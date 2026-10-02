"""Provider boundaries. Only local mock implementations are enabled."""
from typing import Protocol

class HoldingsAdapter(Protocol):
    def fetch_holdings(self, connection, account_id: str) -> list[dict]: ...

class MarketDataAdapter(Protocol):
    def snapshot(self, dataset: dict) -> dict: ...

class ExecutionAdapter(Protocol):
    def submit(self, *, client_order_id: str, account_id: str, isin: str, quantity: int, price: float, order_type: str) -> dict: ...

class MockHoldingsAdapter:
    def fetch_holdings(self, connection, account_id):
        return [dict(r) for r in connection.execute('SELECT * FROM holdings WHERE account_id=?', (account_id,))]

class MockMarketDataAdapter:
    def snapshot(self, dataset): return dataset

class MockExecutionAdapter:
    """No network calls. Immediate fill at snapshot price, without fees or slippage."""
    def submit(self, *, client_order_id, account_id, isin, quantity, price, order_type):
        if quantity <= 0: raise ValueError('Order quantity must be positive.')
        if order_type != 'MARKET': raise ValueError('MVP simulation supports market orders only.')
        return {'broker_order_id': 'SIM-' + client_order_id, 'status': 'SIMULATED_FILLED', 'filled_quantity': quantity, 'fill_price': price}
