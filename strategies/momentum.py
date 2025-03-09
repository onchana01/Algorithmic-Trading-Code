
import pandas as pd
from utils.logger import setup_logger

class MomentumStrategy:
    def __init__(self, window: int = 10):
        self.window = window
        self.logger = setup_logger(__name__)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:

        # Generate buy/sell signals based on momentum.

        df["momentum"] = df["close"].pct_change(periods=self.window)
        df["signal"] = 0
        df.loc[df["momentum"] > 0, "signal"] = 1  
        df.loc[df["momentum"] < 0, "signal"] = -1  
        self.logger.info(f"Generated momentum signals with window={self.window}")
        return df