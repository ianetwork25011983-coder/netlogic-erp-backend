from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import Deposito
from apps.products.models import Lote, Producto

from .models import CapaCosto, MovimientoInventario, StockBalance, StockReserva, Ubicacion
from .serializers import (
    AjusteInputSerializer,
    CapaCostoSerializer,
    ConteoFisicoInputSerializer,
    EntradaInputSerializer,
    MovimientoInventarioSerializer,
    SalidaInputSerializer,
    StockBalanceSerializer,
    StockReservaSerializer,
    TransferenciaInputSerializer,
    UbicacionSerializer,
)
from .services import InventoryError, InventoryService


class ScopedToEmpresaMixin:
    empresa_lookup = "producto__empresa"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(**{self.empresa_lookup: user.empresa})


class UbicacionViewSet(viewsets.ModelViewSet):
    queryset = Ubicacion.objects.select_related("deposito")
    serializer_class = UbicacionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_superuser:
            qs = qs.filter(deposito__sucursal__empresa=user.empresa)
        return qs


class StockBalanceViewSet(ScopedToEmpresaMixin, viewsets.ReadOnlyModelViewSet):
    """Saldos actuales — solo lectura: se generan exclusivamente vía InventoryService."""

    queryset = StockBalance.objects.select_related("producto", "deposito", "lote")
    serializer_class = StockBalanceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["producto", "deposito"]


class StockReservaViewSet(ScopedToEmpresaMixin, viewsets.ReadOnlyModelViewSet):
    queryset = StockReserva.objects.select_related("producto", "deposito")
    serializer_class = StockReservaSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["producto", "deposito", "active", "referencia_tipo"]


class CapaCostoViewSet(ScopedToEmpresaMixin, viewsets.ReadOnlyModelViewSet):
    queryset = CapaCosto.objects.select_related("producto", "deposito", "lote")
    serializer_class = CapaCostoSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["producto", "deposito"]


class MovimientoInventarioViewSet(ScopedToEmpresaMixin, viewsets.ReadOnlyModelViewSet):
    """Kardex — solo lectura: todo movimiento se crea vía los endpoints de acción de abajo."""

    queryset = MovimientoInventario.objects.select_related("producto", "deposito", "lote", "usuario")
    serializer_class = MovimientoInventarioSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["producto", "deposito", "tipo_movimiento", "lote"]


def _get_scoped_producto(request, producto_id):
    qs = Producto.objects.all() if request.user.is_superuser else Producto.objects.filter(empresa=request.user.empresa)
    return get_object_or_404(qs, pk=producto_id)


class EntradaInventarioView(APIView):
    """POST /api/inventory/movimientos/entrada/ -- registra una entrada de stock."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = EntradaInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        producto = _get_scoped_producto(request, data["producto"])
        deposito = get_object_or_404(Deposito, pk=data["deposito"])
        lote = get_object_or_404(Lote, pk=data["lote"]) if data.get("lote") else None

        try:
            movimiento = InventoryService.registrar_entrada(
                producto=producto, deposito=deposito, cantidad=data["cantidad"],
                costo_unitario=data["costo_unitario"], moneda_costo_code=data["moneda_costo_code"],
                usuario=request.user, lote=lote, documento_tipo=data.get("documento_tipo", ""),
                documento_referencia=data.get("documento_referencia", ""),
                observaciones=data.get("observaciones", ""),
            )
        except InventoryError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(MovimientoInventarioSerializer(movimiento).data, status=status.HTTP_201_CREATED)


class SalidaInventarioView(APIView):
    """POST /api/inventory/movimientos/salida/ -- registra una salida de stock."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = SalidaInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        producto = _get_scoped_producto(request, data["producto"])
        deposito = get_object_or_404(Deposito, pk=data["deposito"])
        lote = get_object_or_404(Lote, pk=data["lote"]) if data.get("lote") else None

        try:
            movimiento = InventoryService.registrar_salida(
                producto=producto, deposito=deposito, cantidad=data["cantidad"], usuario=request.user,
                lote=lote, documento_tipo=data.get("documento_tipo", ""),
                documento_referencia=data.get("documento_referencia", ""),
                observaciones=data.get("observaciones", ""),
            )
        except InventoryError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(MovimientoInventarioSerializer(movimiento).data, status=status.HTTP_201_CREATED)


class TransferenciaInventarioView(APIView):
    """POST /api/inventory/movimientos/transferencia/ -- mueve stock entre depósitos."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = TransferenciaInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        producto = _get_scoped_producto(request, data["producto"])
        deposito_origen = get_object_or_404(Deposito, pk=data["deposito_origen"])
        deposito_destino = get_object_or_404(Deposito, pk=data["deposito_destino"])
        lote = get_object_or_404(Lote, pk=data["lote"]) if data.get("lote") else None

        try:
            mov_salida, mov_entrada = InventoryService.registrar_transferencia(
                producto=producto, deposito_origen=deposito_origen, deposito_destino=deposito_destino,
                cantidad=data["cantidad"], usuario=request.user, lote=lote,
                documento_referencia=data.get("documento_referencia", ""),
                observaciones=data.get("observaciones", ""),
            )
        except InventoryError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "salida": MovimientoInventarioSerializer(mov_salida).data,
                "entrada": MovimientoInventarioSerializer(mov_entrada).data,
            },
            status=status.HTTP_201_CREATED,
        )


class AjusteInventarioView(APIView):
    """POST /api/inventory/movimientos/ajuste/ -- ajuste manual positivo o negativo."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AjusteInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        producto = _get_scoped_producto(request, data["producto"])
        deposito = get_object_or_404(Deposito, pk=data["deposito"])
        lote = get_object_or_404(Lote, pk=data["lote"]) if data.get("lote") else None

        try:
            movimiento = InventoryService.registrar_ajuste(
                producto=producto, deposito=deposito, cantidad_ajuste=data["cantidad_ajuste"],
                motivo=data["motivo"], usuario=request.user, lote=lote,
                costo_unitario_manual=data.get("costo_unitario_manual"),
                moneda_costo_code=data.get("moneda_costo_code") or None,
                documento_referencia=data.get("documento_referencia", ""),
            )
        except InventoryError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(MovimientoInventarioSerializer(movimiento).data, status=status.HTTP_201_CREATED)


class ConteoFisicoInventarioView(APIView):
    """POST /api/inventory/movimientos/conteo-fisico/ -- genera el ajuste por diferencia de conteo."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ConteoFisicoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        producto = _get_scoped_producto(request, data["producto"])
        deposito = get_object_or_404(Deposito, pk=data["deposito"])
        lote = get_object_or_404(Lote, pk=data["lote"]) if data.get("lote") else None

        try:
            movimiento = InventoryService.registrar_conteo_fisico(
                producto=producto, deposito=deposito, cantidad_contada=data["cantidad_contada"],
                usuario=request.user, lote=lote, documento_referencia=data.get("documento_referencia", ""),
            )
        except InventoryError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if movimiento is None:
            return Response({"detail": "El conteo coincide con el sistema; no se generó ajuste."}, status=status.HTTP_200_OK)

        return Response(MovimientoInventarioSerializer(movimiento).data, status=status.HTTP_201_CREATED)


class KardexView(APIView):
    """GET /api/inventory/kardex/?producto=<id>&deposito=<id>&lote=<id> -- historial completo de un producto."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        producto_id = request.query_params.get("producto")
        if not producto_id:
            return Response({"detail": "El parámetro 'producto' es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)

        producto = _get_scoped_producto(request, producto_id)
        deposito = None
        if request.query_params.get("deposito"):
            deposito = get_object_or_404(Deposito, pk=request.query_params["deposito"])
        lote = None
        if request.query_params.get("lote"):
            lote = get_object_or_404(Lote, pk=request.query_params["lote"])

        movimientos = InventoryService.get_kardex(producto, deposito=deposito, lote=lote)
        return Response(MovimientoInventarioSerializer(movimientos, many=True).data)


class ValorizacionInventarioView(APIView):
    """GET /api/inventory/valorizacion/?deposito=<id>&categoria=<id> -- inventario valorizado."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        empresa = None if request.user.is_superuser else request.user.empresa
        deposito = None
        if request.query_params.get("deposito"):
            deposito = get_object_or_404(Deposito, pk=request.query_params["deposito"])

        saldos = InventoryService.get_valorizacion(empresa=empresa, deposito=deposito)
        data = StockBalanceSerializer(saldos, many=True).data
        total_pyg = sum(s.valor_total_pyg for s in saldos)
        return Response({"items": data, "valor_total_pyg": total_pyg})
