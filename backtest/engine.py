
import backtrader as bt
from utils.logger import setup_logger

class BacktestEngine:
    def __init__(self, cash: float = 10000.0, commission: float = 0.001):
        self.cash = cash
        self.commission = commission
        self.logger = setup_logger(__name__)

    def run_backtest(self, data: bt.feeds.PandasData, strategy: bt.Strategy) -> bt.Cerebro:
        cerebro = bt.Cerebro()
        cerebro.addstrategy(strategy)
        cerebro.adddata(data)
        cerebro.broker.setcash(self.cash)
        cerebro.broker.setcommission(commission=self.commission)
        
        self.logger.info("Starting backtest...")
        cerebro.run()
        self.logger.info(f"Final portfolio value: {cerebro.broker.getvalue():.2f}")
        return cerebro

class MomentumBTStrategy(bt.Strategy):
    params = (("window", 10),)
    def __init__(self):
        self.momentum = bt.indicators.PercentChange(period=self.params.window)
        self.logger = setup_logger(__name__)

    def next(self):
        if self.momentum[0] > 0:
            self.buy()
        elif self.momentum[0] < 0:
            self.sell()