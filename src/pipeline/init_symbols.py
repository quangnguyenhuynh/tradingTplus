from datetime import datetime
from typing import Any
from src.ssi.api import SSIApi
from src.database.client import SupabaseClient


def _get_any(data: dict, *keys: str) -> Any:
    lower = {str(k).lower(): v for k, v in (data or {}).items()}
    for key in keys:
        if key in data:
            return data.get(key)
        if key.lower() in lower:
            return lower[key.lower()]
    return None


def _to_num(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_date(value):
    if value in (None, ""):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _security_record(item: dict) -> dict | None:
    symbol = _get_any(item, 'Symbol', 'symbol')
    if not symbol:
        return None
    return {
        'symbol': symbol,
        'market': _get_any(item, 'Market', 'market'),
        'stock_name': _get_any(item, 'StockName', 'stockName', 'Name'),
        'stock_en_name': _get_any(item, 'StockEnName', 'stockEnName'),
        'sec_type': _get_any(item, 'SecType', 'secType'),
        'exchange': _get_any(item, 'Exchange', 'exchange'),
        'issuer': _get_any(item, 'Issuer', 'issuer'),
        'lot_size': _to_num(_get_any(item, 'LotSize', 'lotSize')),
        'issue_date': _to_date(_get_any(item, 'IssueDate', 'issueDate')),
        'maturity_date': _to_date(_get_any(item, 'MaturityDate', 'maturityDate')),
        'first_trading_date': _to_date(_get_any(item, 'FirstTradingDate', 'firstTradingDate')),
        'last_trading_date': _to_date(_get_any(item, 'LastTradingDate', 'lastTradingDate')),
        'listed_share': _to_num(_get_any(item, 'ListedShare', 'listedShare')),
        'tick_price1': _to_num(_get_any(item, 'TickPrice1', 'tickPrice1')),
        'tick_increment1': _to_num(_get_any(item, 'TickIncrement1', 'tickIncrement1')),
        'tick_price2': _to_num(_get_any(item, 'TickPrice2', 'tickPrice2')),
        'tick_increment2': _to_num(_get_any(item, 'TickIncrement2', 'tickIncrement2')),
        'tick_price3': _to_num(_get_any(item, 'TickPrice3', 'tickPrice3')),
        'tick_increment3': _to_num(_get_any(item, 'TickIncrement3', 'tickIncrement3')),
        'tick_price4': _to_num(_get_any(item, 'TickPrice4', 'tickPrice4')),
        'tick_increment4': _to_num(_get_any(item, 'TickIncrement4', 'tickIncrement4')),
        'raw': item,
    }


def init_symbols():
    print("📋 Đang lấy danh sách mã từ SSI...")
    ssi = SSIApi()
    db = SupabaseClient()
    data = ssi.get_symbols()
    symbols = [{'symbol': item['Symbol'], 'market': item.get('Market'), 'name': item.get('StockName', '')} for item in data if item.get('Symbol')]
    db.upsert_symbols(symbols)

    details = []
    for market in ["HOSE", "HNX", "UPCOM", "DER"]:
        details.extend(ssi.get_security_details(market=market))
    by_symbol = {rec['symbol']: rec for rec in (_security_record(item) for item in details) if rec}
    for item in data:
        symbol = item.get('Symbol')
        if symbol and symbol not in by_symbol:
            by_symbol[symbol] = _security_record(item) or {'symbol': symbol, 'market': item.get('Market'), 'raw': item}
    securities = list(by_symbol.values())
    db.upsert_securities(securities)
    print(f"✅ Đã lưu {len(symbols)} mã vào symbols và {len(securities)} mã vào securities")
