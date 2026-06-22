import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.currencies.models import Currency, ExchangeRate
from apps.currencies.services import CurrencyService, NoExchangeRateFoundError


@pytest.mark.django_db
class TestCurrency:
    def test_solo_puede_haber_una_moneda_base(self, pyg):
        with pytest.raises(ValidationError):
            Currency.objects.create(code="USD", name="Dólar", symbol="$", decimal_places=2, is_base=True)

    def test_get_base_devuelve_la_moneda_marcada(self, pyg):
        assert Currency.get_base() == pyg


@pytest.mark.django_db
class TestExchangeRate:
    def test_no_se_puede_cargar_tasa_para_la_moneda_base(self, pyg):
        with pytest.raises(ValidationError):
            ExchangeRate.objects.create(currency=pyg, rate_to_base=Decimal("1"), effective_date=datetime.date.today())

    def test_tasa_debe_ser_positiva(self, usd):
        with pytest.raises(ValidationError):
            ExchangeRate.objects.create(currency=usd, rate_to_base=Decimal("-5"), effective_date=datetime.date.today())


@pytest.mark.django_db
class TestCurrencyService:
    def test_convert_to_base_usd_a_pyg(self, usd):
        resultado = CurrencyService.convert_to_base(Decimal("100"), "USD")
        assert resultado == Decimal("750000")

    def test_convert_cruzado_usd_a_brl(self, usd):
        brl = Currency.objects.create(code="BRL", name="Real", symbol="R$", decimal_places=2)
        ExchangeRate.objects.create(currency=brl, rate_to_base=Decimal("1380"), effective_date=datetime.date.today())

        resultado = CurrencyService.convert(Decimal("100"), "USD", "BRL")
        assert resultado == Decimal("543.48")

    def test_sin_tasa_cargada_lanza_excepcion(self, pyg):
        Currency.objects.create(code="EUR", name="Euro", symbol="€", decimal_places=2)
        with pytest.raises(NoExchangeRateFoundError):
            CurrencyService.get_rate("EUR")

    def test_usa_la_tasa_vigente_a_una_fecha_pasada_no_la_mas_reciente(self, usd):
        ExchangeRate.objects.create(
            currency=usd, rate_to_base=Decimal("8000"),
            effective_date=datetime.date.today() + datetime.timedelta(days=5),
        )
        tasa_hoy = CurrencyService.get_rate("USD", datetime.date.today())
        assert tasa_hoy == Decimal("7500.000000")

    def test_misma_moneda_no_convierte(self, usd):
        resultado = CurrencyService.convert(Decimal("50"), "USD", "USD")
        assert resultado == Decimal("50")
