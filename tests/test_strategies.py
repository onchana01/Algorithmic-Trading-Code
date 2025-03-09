
import pytest
import pandas as pd
from strategies.momentum import MomentumStrategy

def test_momentum_strategy():
    df = pd.DataFrame({
        "time": pd.date_range("2023-01-01", periods=15, freq="1min"),
        "close": [100, 101, 102, 103, 104, 105, 106, 105, 104, 103, 102, 101, 100, 99, 98]
    })
    strategy = MomentumStrategy(window=5)
    df_with_signals = strategy.generate_signals(df)
    assert "signal" in df_with_signals.columns
    assert df_with_signals["signal"].iloc[-1] == -1  # Last signal should be sell