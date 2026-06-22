from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Currency, ExchangeRate
from .serializers import ConvertAmountSerializer, CurrencySerializer, ExchangeRateSerializer
from .services import CurrencyConversionError, CurrencyService


class CurrencyViewSet(viewsets.ModelViewSet):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    permission_classes = [permissions.IsAuthenticated]


class ExchangeRateViewSet(viewsets.ModelViewSet):
    queryset = ExchangeRate.objects.select_related("currency", "loaded_by")
    serializer_class = ExchangeRateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(loaded_by=self.request.user)


class ConvertAmountView(APIView):
    """
    POST /api/currencies/convert/
    {"amount": "100.00", "from_currency": "USD", "to_currency": "PYG"}
    Usado por facturación/compras/inventario para no reimplementar la
    lógica de conversión en cada módulo.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ConvertAmountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            result = CurrencyService.convert(
                data["amount"], data["from_currency"], data["to_currency"], data.get("as_of_date")
            )
        except CurrencyConversionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "amount": data["amount"],
                "from_currency": data["from_currency"],
                "to_currency": data["to_currency"],
                "converted_amount": result,
            }
        )
