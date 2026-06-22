"""
Servicio de conversión de monedas.

Cualquier módulo del ERP que necesite trabajar con montos en distintas
monedas (facturación, compras, costos de inventario) debe pasar por este
servicio en lugar de calcular conversiones manualmente. Esto centraliza
la lógica de "tasa vigente a una fecha" y evita inconsistencias.
"""
from datetime import date as date_cls
from decimal import ROUND_HALF_UP, Decimal

from django.core.cache import cache

from .models import Currency, ExchangeRate


class CurrencyConversionError(Exception):
    pass


class NoExchangeRateFoundError(CurrencyConversionError):
    def __init__(self, currency_code, as_of_date):
        self.currency_code = currency_code
        self.as_of_date = as_of_date
        super().__init__(
            f"No hay tasa de cambio cargada para {currency_code} "
            f"vigente al {as_of_date}. Cargue una tasa antes de continuar."
        )


class CurrencyService:
    CACHE_TTL_SECONDS = 60 * 15  # 15 min; las tasas se cargan manualmente, no cambian seguido

    @staticmethod
    def get_base_currency() -> Currency:
        return Currency.get_base()

    @classmethod
    def get_rate(cls, currency_code: str, as_of_date: date_cls = None) -> Decimal:
        """
        Devuelve la tasa de conversión a la moneda base vigente en
        `as_of_date` (la última tasa cargada con effective_date <= as_of_date).
        """
        as_of_date = as_of_date or date_cls.today()

        currency = Currency.objects.get(code=currency_code, active=True)
        if currency.is_base:
            return Decimal("1")

        cache_key = f"fx_rate:{currency_code}:{as_of_date.isoformat()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Decimal(cached)

        rate = (
            ExchangeRate.objects.filter(currency=currency, effective_date__lte=as_of_date)
            .order_by("-effective_date")
            .first()
        )
        if rate is None:
            raise NoExchangeRateFoundError(currency_code, as_of_date)

        cache.set(cache_key, str(rate.rate_to_base), cls.CACHE_TTL_SECONDS)
        return rate.rate_to_base

    @classmethod
    def convert_to_base(cls, amount: Decimal, currency_code: str, as_of_date: date_cls = None) -> Decimal:
        rate = cls.get_rate(currency_code, as_of_date)
        base = Currency.get_base()
        result = (Decimal(amount) * rate).quantize(
            Decimal(10) ** -base.decimal_places, rounding=ROUND_HALF_UP
        )
        return result

    @classmethod
    def convert(cls, amount: Decimal, from_currency_code: str, to_currency_code: str, as_of_date: date_cls = None) -> Decimal:
        if from_currency_code == to_currency_code:
            return Decimal(amount)

        amount_in_base = cls.convert_to_base(amount, from_currency_code, as_of_date)

        if to_currency_code == Currency.get_base().code:
            return amount_in_base

        target_rate = cls.get_rate(to_currency_code, as_of_date)
        target_currency = Currency.objects.get(code=to_currency_code)
        result = (amount_in_base / target_rate).quantize(
            Decimal(10) ** -target_currency.decimal_places, rounding=ROUND_HALF_UP
        )
        return result
