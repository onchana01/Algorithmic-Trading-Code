from utils.data_handler import DataHandler
from strategies.momentum import MomentumStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.arbitrage import ArbitrageStrategy
from backtest.engine import BacktestEngine, MomentumBTStrategy
import backtrader as bt
import pandas as pd
from utils.logger import setup_logger
import asyncio
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
from dash import Dash, html, dcc, Input, Output
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def run_backtest(data_handler, ticker1, logger):
    # Run backtest on historical data 
    df_from_influx1 = data_handler.query_influxdb(ticker1, start_time="-5d")
    if df_from_influx1 is None:
        logger.error(f"Failed to retrieve data for {ticker1}. Exiting backtest.")
        return
    
    # Prepare data for backtrader
    df_bt = df_from_influx1.rename(columns={"time": "datetime"})
    df_bt['datetime'] = pd.to_datetime(df_bt['datetime'], utc=True)
    df_bt = df_bt[['datetime', 'open', 'high', 'low', 'close', 'volume']]
    df_bt = df_bt.dropna()
    
    logger.info(f"Backtrader DataFrame dtypes:\n{df_bt.dtypes}")
    logger.info(f"Sample data:\n{df_bt.head()}")
    
    data_feed = bt.feeds.PandasData(
        dataname=df_bt,
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5
    )
    
    # Backtest momentum strategy
    engine = BacktestEngine(cash=10000.0, commission=0.001)
    cerebro = engine.run_backtest(data_feed, MomentumBTStrategy)
    
    # backtest plot
    cerebro.plot()
    

async def run_realtime(data_handler, ticker1, ticker2, api_key, secret_key, logger):
    # Run real-time streaming and signal generation.
    # Strategies
    momentum = MomentumStrategy(window=10)
    mean_reversion = MeanReversionStrategy(window=20)
    arbitrage = ArbitrageStrategy(ticker1, ticker2, threshold=0.005)
    
    # Buffers for real-time data
    buffer1 = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    buffer2 = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    
    async def process_stream(ticker, buffer):
        # Process streamed data and generate signals.
        while True:
            df = data_handler.query_influxdb(ticker, start_time="-5m")
            if df is not None and not df.empty:
                buffer = pd.concat([buffer, df]).drop_duplicates(subset="time").tail(100)
                if ticker == ticker1:
                    df_momentum = momentum.generate_signals(buffer.copy())
                    df_mean_reversion = mean_reversion.generate_signals(buffer.copy())
                    logger.info(f"{ticker} Momentum signal: {df_momentum['signal'].iloc[-1]}")
                    logger.info(f"{ticker} Mean-reversion signal: {df_mean_reversion['signal'].iloc[-1]}")
                if ticker == ticker2 and not buffer1.empty:
                    df_arbitrage = arbitrage.generate_signals(buffer1, buffer)
                    logger.info(f"Arbitrage signal: {df_arbitrage['signal'].iloc[-1]}")
            await asyncio.sleep(60) 
    
    # Start streaming and processing tasks
    stream_task1 = asyncio.create_task(data_handler.stream_to_influxdb(ticker1, api_key, secret_key))
    stream_task2 = asyncio.create_task(data_handler.stream_to_influxdb(ticker2, api_key, secret_key))
    process_task1 = asyncio.create_task(process_stream(ticker1, buffer1))
    process_task2 = asyncio.create_task(process_stream(ticker2, buffer2))
    
    await asyncio.gather(stream_task1, stream_task2, process_task1, process_task2)

# Dash app
app = Dash(__name__)

def main():
    logger = setup_logger(__name__)
    ticker1 = "AAPL"
    ticker2 = "SPY"
    
    # Alpaca API credentials 
    ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "default-key-if-not-set")
    ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "default-secret-if-not-set")

    # Echo the credentials
    logger.info(f"ALPACA_API_KEY: {ALPACA_API_KEY}")
    logger.info(f"ALPACA_SECRET_KEY: {ALPACA_SECRET_KEY}")
    
    # Initialize data handler
    data_handler = DataHandler()
    
    # Mode selection
    RUN_BACKTEST = True
    RUN_REALTIME = False
    
    if RUN_BACKTEST:
        # Fetch and store historical data
        logger.info(f"Fetching historical data for {ticker1} and {ticker2}")
        df1 = data_handler.fetch_yfinance_data(ticker1, period="5d", interval="1m")
        df2 = data_handler.fetch_yfinance_data(ticker2, period="5d", interval="1m")
        
        logger.info(f"{ticker1} data shape: {df1.shape}, {ticker2} data shape: {df2.shape}")
        data_handler.write_to_influxdb(df1, ticker1)
        data_handler.write_to_influxdb(df2, ticker2)
        
        # Run strategies on historical data
        df_from_influx1 = data_handler.query_influxdb(ticker1, start_time="-5d")
        df_from_influx2 = data_handler.query_influxdb(ticker2, start_time="-5d")
        if df_from_influx1 is None or df_from_influx2 is None:
            logger.error("Failed to retrieve data. Exiting.")
            return
        
        momentum = MomentumStrategy(window=10)
        mean_reversion = MeanReversionStrategy(window=20)
        arbitrage = ArbitrageStrategy(ticker1, ticker2, threshold=0.005)
        
        df_momentum = momentum.generate_signals(df_from_influx1.copy())
        df_mean_reversion = mean_reversion.generate_signals(df_from_influx1.copy())
        df_arbitrage = arbitrage.generate_signals(df_from_influx1, df_from_influx2)
        
        logger.info(f"Momentum signals (last 5):\n{df_momentum[['time', 'close', 'momentum', 'signal']].tail()}")
        logger.info(f"Mean-reversion signals (last 5):\n{df_mean_reversion[['time', 'close', 'sma', 'signal']].tail()}")
        logger.info(f"Arbitrage signals (last 5):\n{df_arbitrage[['time', 'close_ticker1', 'close_ticker2', 'spread', 'signal']].tail()}")
        
        # Run backtest
        run_backtest(data_handler, ticker1, logger)
    else:
        # Run real-time streaming
        asyncio.run(run_realtime(data_handler, ticker1, ticker2, ALPACA_API_KEY, ALPACA_SECRET_KEY, logger))
    
    # Dash layout
    app.layout = html.Div([
        html.H1("Algorithmic Trading Dashboard"),
        dcc.Interval(id='interval-component', interval=60*1000, n_intervals=0),
        html.Div([
            html.H3(f"{ticker1} Signals"),
            dcc.Graph(id='ticker1-plot'),
        ]),
        html.Div([
            html.H3(f"{ticker2} vs {ticker1} Arbitrage"),
            dcc.Graph(id='arbitrage-plot'),
        ]),
    ])

    @app.callback(
        [Output('ticker1-plot', 'figure'),
         Output('arbitrage-plot', 'figure')],
        [Input('interval-component', 'n_intervals')]
    )
    def update_plots(n):
        df1 = data_handler.query_influxdb(ticker1, start_time="-1h")
        df2 = data_handler.query_influxdb(ticker2, start_time="-1h")
        
        if df1 is None or df2 is None:
            logger.error("Failed to retrieve data for plotting.")
            return go.Figure(), go.Figure()

        momentum = MomentumStrategy(window=10)
        mean_reversion = MeanReversionStrategy(window=20)
        arbitrage = ArbitrageStrategy(ticker1, ticker2, threshold=0.005)
        
        df_momentum = momentum.generate_signals(df1.copy())
        df_mean_reversion = mean_reversion.generate_signals(df1.copy())
        df_arbitrage = arbitrage.generate_signals(df1, df2)

        fig1 = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            subplot_titles=("Momentum Signals", "Mean-Reversion Signals"))
        fig1.add_trace(go.Scatter(x=df_momentum['time'], y=df_momentum['close'], mode='lines', name='Close'), row=1, col=1)
        fig1.add_trace(go.Scatter(x=df_momentum['time'], y=df_momentum['signal'] * df_momentum['close'].max(), 
                                mode='markers', name='Momentum Signal', marker=dict(color='red')), row=1, col=1)
        fig1.add_trace(go.Scatter(x=df_mean_reversion['time'], y=df_mean_reversion['close'], mode='lines', name='Close'), row=2, col=1)
        fig1.add_trace(go.Scatter(x=df_mean_reversion['time'], y=df_mean_reversion['signal'] * df_mean_reversion['close'].max(), 
                                mode='markers', name='Mean-Reversion Signal', marker=dict(color='green')), row=2, col=1)
        fig1.update_layout(height=600, title_text=f"{ticker1} Multi-Strategy Comparison")

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=df_arbitrage['time'], y=df_arbitrage['spread'], mode='lines', name='Spread'))
        fig2.add_trace(go.Scatter(x=df_arbitrage['time'], y=df_arbitrage['signal'] * df_arbitrage['spread'].max(), 
                                mode='markers', name='Arbitrage Signal', marker=dict(color='purple')))
        fig2.update_layout(title=f"Arbitrage Spread: {ticker1} vs {ticker2}", yaxis_title="Spread")

        return fig1, fig2

    # Run Dash server
    app.run_server(debug=True, host='0.0.0.0', port=8050)
    
    data_handler.close()

if __name__ == "__main__":
    main()