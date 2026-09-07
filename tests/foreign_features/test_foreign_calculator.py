from decimal import Decimal
import random
import pytest

from src.foreign_features.calendar import TradingCalendar
from src.foreign_features.calculator import calculate_symbol
from src.foreign_features.validator import decimal_value, validate_source_row


def cal(n=20):
    sessions=tuple(f"2026-08-{i:02d}" for i in range(1,n+1))
    return TradingCalendar(sessions,"fixture","HOSE","calendar-hash")


def row(day,b,s,v,symbol="SSI"):
    return {"symbol":symbol,"trading_date":day,"foreign_buy_val_total":b,"foreign_sell_val_total":s,"net_foreign_val":Decimal(str(b))-Decimal(str(s)),"total_traded_value":v,
            "foreign_buy_vol_total":b,"foreign_sell_vol_total":s,"net_foreign_vol":Decimal(str(b))-Decimal(str(s))}


def test_required_hand_calculated_fixture():
    c=cal(5); inputs=[row(d,b,s,v) for d,b,s,v in zip(c.sessions,[100,0,30,0,20],[0,50,10,0,0],[1000,100,200,0,100])]
    out=calculate_symbol(inputs,c,c.sessions[-1])
    assert out["net_value_5d"] == Decimal(90)
    assert out["activity_value_5d"] == Decimal(210)
    assert out["net_value_ratio_5d"] == Decimal(90)/Decimal(1400)
    assert out["activity_ratio_5d"] == Decimal(210)/Decimal(2800)
    assert (out["buy_days_5d"],out["sell_days_5d"]) == (3,1)


def test_large_money_20_and_non_overlapping_change_and_shuffle():
    c=cal(20); inputs=[row(d,10**30+i,10**30,10**32) for i,d in enumerate(c.sessions,1)]
    random.Random(3).shuffle(inputs)
    out=calculate_symbol(inputs,c,c.sessions[-1])
    assert out["net_value_20d"] == sum(range(1,21))
    assert out["net_value_ratio_change_5d"] == Decimal(sum(range(16,21))-sum(range(11,16)))/Decimal(5*10**32)


def test_duplicate_rejected_and_symbols_are_isolated_by_caller():
    c=cal(5); inputs=[row(d,1,0,10) for d in c.sessions]
    with pytest.raises(ValueError,match="DUPLICATE_SOURCE"):
        calculate_symbol(inputs+[dict(inputs[-1])],c,c.sessions[-1])

@pytest.mark.parametrize("bad",[True,float("nan"),float("inf"),float("-inf"),"x"])
def test_non_finite_boolean_and_invalid_numbers(bad):
    with pytest.raises(ValueError): decimal_value(bad)


def test_net_and_volume_mismatch_are_separate():
    r=row("2026-08-01",10,2,100); r["net_foreign_val"]=7; r["net_foreign_vol"]=9
    reasons=validate_source_row(r)
    assert "NET_VALUE_MISMATCH" in reasons and "NET_VOLUME_MISMATCH" in reasons


def test_volume_mismatch_does_not_invalidate_value_features():
    c=cal(5); inputs=[row(d,2,1,10) for d in c.sessions]
    inputs[-1]["net_foreign_vol"] = 999
    out=calculate_symbol(inputs,c,c.sessions[-1])
    assert out["net_value_5d"] == 5
    assert out["quality_status"]["5"]["status"] == "PARTIAL"
    assert "NET_VOLUME_MISMATCH" in out["quality_status"]["5"]["reasons"]


def test_zero_trading_and_impossible_activity():
    c=cal(5); zero=[row(d,0,0,0) for d in c.sessions]
    out=calculate_symbol(zero,c,c.sessions[-1])
    assert out["net_value_5d"] == 0 and out.get("net_value_ratio_5d") is None
    assert "DENOMINATOR_ZERO" in out["quality_status"]["5"]["reasons"]
    assert "FOREIGN_ACTIVITY_WITH_ZERO_TURNOVER" in validate_source_row(row(c.sessions[-1],1,0,0))


def test_missing_session_is_not_replaced_by_older_day():
    c=cal(20); inputs=[row(d,1,0,10) for d in c.sessions if d != c.sessions[-3]]
    out=calculate_symbol(inputs,c,c.sessions[-1])
    assert out["quality_status"]["5"]["status"] == "MISSING_SOURCE"
    assert out.get("net_value_5d") is None
