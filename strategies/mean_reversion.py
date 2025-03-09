
import pandas as pd
from utils.logger import setup_logger

class MeanReversionStrategy:
    def __init__(self, window: int = 20, std_dev: float = 2.0):
        self.window = window
        self.std_dev = std_dev
        self.logger = setup_logger(__name__)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:

        # Generate buy/sell signals based on Bollinger Bands.

        df["sma"] = df["close"].rolling(window=self.window).mean()
        df["std"] = df["close"].rolling(window=self.window).std()
        df["upper_band"] = df["sma"] + (self.std_dev * df["std"])
        df["lower_band"] = df["sma"] - (self.std_dev * df["std"])
        
        df["signal"] = 0
        df.loc[df["close"] < df["lower_band"], "signal"] = 1  
        df.loc[df["close"] > df["upper_band"], "signal"] = -1  
        self.logger.info(f"Generated mean-reversion signals with window={self.window}")
        return df