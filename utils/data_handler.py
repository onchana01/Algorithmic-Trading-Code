# utils/data_handler.py
from typing import Optional
import yfinance as yf
import pandas as pd
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from utils.logger import setup_logger
from alpaca.data.live import StockDataStream
import asyncio
import os

INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = os.environ.get("INFLUXDB_TOKEN")
INFLUX_ORG = "onchana"
INFLUX_BUCKET = "trading_data"

class DataHandler:
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()

    def fetch_yfinance_data(self, ticker: str, period: str = "1d", interval: str = "1m") -> pd.DataFrame:
        self.logger.info(f"Fetching data for {ticker}...")
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        df.reset_index(inplace=True)
        df.rename(columns={"Datetime": "time"}, inplace=True)
        return df[["time", "Open", "High", "Low", "Close", "Volume"]]

    def write_to_influxdb(self, df: pd.DataFrame, ticker: str, measurement: str = "stock_data"):
        self.logger.info(f"Writing data for {ticker} to InfluxDB...")
        points = [
            Point(measurement)
            .tag("ticker", ticker)
            .field("open", float(row["Open"]))
            .field("high", float(row["High"]))
            .field("low", float(row["Low"]))
            .field("close", float(row["Close"]))
            .field("volume", int(row["Volume"]))
            .time(row["time"])
            for _, row in df.iterrows()
        ]
        self.write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points)

    def query_influxdb(self, ticker: str, start_time: str = "-1d") -> Optional[pd.DataFrame]:
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
            |> range(start: {start_time})
            |> filter(fn: (r) => r["_measurement"] == "stock_data")
            |> filter(fn: (r) => r["ticker"] == "{ticker}")
            |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        self.logger.info(f"Querying data for {ticker} with query: {query}")
        try:
            result = self.query_api.query_data_frame(query)
            self.logger.info(f"Query result shape: {result.shape if not result.empty else 'empty'}")
            self.logger.info(f"Query result columns: {list(result.columns) if not result.empty else 'none'}")
            if result.empty:
                self.logger.warning(f"No data returned for {ticker}")
                return None
            result.drop(columns=["result", "table"], inplace=True, errors="ignore")
            if "_time" not in result.columns:
                self.logger.error(f"'_time' column missing in query result: {list(result.columns)}")
                return None
            result.rename(columns={"_time": "time"}, inplace=True)
            result['time'] = pd.to_datetime(result['time'], utc=True, errors='coerce')
            return result[["time", "close", "open", "high", "low", "volume"]]
        except Exception as e:
            self.logger.error(f"Query failed: {str(e)}")
            return None

    async def stream_to_influxdb(self, ticker: str, api_key: str, secret_key: str):
        self.logger.info(f"Starting real-time stream for {ticker}...")
        stream = StockDataStream(api_key, secret_key)
        
        async def handle_bar(bar):
            data = {
                "time": pd.Timestamp(bar.timestamp, tz="UTC"),
                "Open": bar.open,
                "High": bar.high,
                "Low": bar.low,
                "Close": bar.close,
                "Volume": bar.volume
            }
            df = pd.DataFrame([data])
            self.write_to_influxdb(df, ticker)
            self.logger.debug(f"Received bar for {ticker}: {data['Close']}")

        stream.subscribe_bars(handle_bar, ticker)
        await stream.run()

    def close(self):
        self.client.close()