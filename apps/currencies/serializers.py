from rest_framework import serializers

from .models import Currency, ExchangeRate


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ["id", "code", "name", "symbol", "decimal_places", "is_base", "active"]


class ExchangeRateSerializer(serializers.ModelSerializer):
    currency_code = serializers.CharField(source="currency.code", read_only=True)

    class Meta:
        model = ExchangeRate
        fields = [
            "id", "currency", "currency_code", "rate_to_base",
            "effective_date", "source", "loaded_by", "notes", "created_at",
        ]
        read_only_fields = ["loaded_by", "created_at"]


class ConvertAmountSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=6)
    from_currency = serializers.CharField(max_length=3)
    to_currency = serializers.CharField(max_length=3)
    as_of_date = serializers.DateField(required=False)
