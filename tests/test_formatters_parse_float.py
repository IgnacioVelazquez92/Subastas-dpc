from app.ui.formatters import DataFormatter


def test_parse_float_accepts_currency_labels():
    assert DataFormatter.parse_float("$ 1.234.567,89") == 1234567.89
    assert DataFormatter.parse_float("ARS 2.500.000") == 2500000.0
    assert DataFormatter.parse_float("usd 1,234.56") == 1234.56
