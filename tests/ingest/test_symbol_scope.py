import pytest

from src.pipeline.symbol_scope import normalize_symbol_scope, resolve_symbol_scope


def test_normalizes_strips_deduplicates_and_preserves_order():
    assert normalize_symbol_scope(["ssi", " HPG ", "SSI", "fpt"]) == ["SSI", "HPG", "FPT"]


def test_none_means_master_symbols():
    class DB:
        def get_symbols(self):
            return ["ssi", " HPG ", "SSI"]
    assert resolve_symbol_scope(DB(), None) == (["SSI", "HPG"], None)


@pytest.mark.parametrize("symbols", [[], ["  ", "\t"], [None]])
def test_explicit_empty_scope_is_invalid(symbols):
    with pytest.raises(ValueError, match="at least one"):
        normalize_symbol_scope(symbols)
