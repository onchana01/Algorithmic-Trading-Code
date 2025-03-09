
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dash import Dash, html, dcc, Input, Output
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils.data_handler import DataHandler
from strategies.momentum import MomentumStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.arbitrage import ArbitrageStrategy
import pandas as pd
from utils.logger import setup_logger

app = Dash(__name__)
logger = setup_logger(__name__)

data_handler = DataHandler()
ticker1 = "AAPL"
ticker2 = "SPY"
momentum = MomentumStrategy(window=10)
mean_reversion = MeanReversionStrategy(window=20)
arbitrage = ArbitrageStrategy(ticker1, ticker2, threshold=0.005)

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
    df1 = data_handler.query_influxdb(ticker1, start_time="-5d")  # Changed to -5d
    df2 = data_handler.query_influxdb(ticker2, start_time="-5d")  # Changed to -5d
    
    if df1 is None or df2 is None:
        logger.error("Failed to retrieve data for plotting.")
        return go.Figure(), go.Figure()

    df_momentum = momentum.generate_signals(df1.copy())
    df_mean_reversion = mean_reversion.generate_signals(df1.copy())
    df_arbitrage = arbitrage.generate_signals(df1, df2)

    fig1 = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                         subplot_titles=("Price with Momentum Signals", "Price with Mean-Reversion Signals"))
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

if __name__ == "__main__":
    app.run_server(debug=True, host='0.0.0.0', port=8051)