
import pandas as pd
from utils.logger import setup_logger

class ArbitrageStrategy:
    def __init__(self, ticker1: str, ticker2: str, threshold: float = 0.02):
        self.ticker1 = ticker1
        self.ticker2 = ticker2
        self.threshold = threshold
        self.logger = setup_logger(__name__)

    def generate_signals(self, df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
        # Merge dataframes on time
        df = pd.merge(df1[['time', 'close']], df2[['time', 'close']], 
                     on='time', suffixes=('_ticker1', '_ticker2'))
        
        # Calculate spread (normalized price difference)
        df['spread'] = (df['close_ticker1'] - df['close_ticker2']) / df['close_ticker2']
        
        # Generate signals
        df['signal'] = 0
        df.loc[df['spread'] > self.threshold, 'signal'] = 1   # Buy ticker1, sell ticker2
        df.loc[df['spread'] < -self.threshold, 'signal'] = -1 # Sell ticker1, buy ticker2
        
        self.logger.info(f"Generated arbitrage signals for {self.ticker1} vs {self.ticker2} "
                        f"with threshold={self.threshold}")
        return df