from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import Deposito, Empresa, PuntoVenta, Sucursal
from apps.customers.models import Cliente
from apps.pricing.models import ListaPrecio

from .models import PedidoWeb
from .serializers import (
    AccionPedidoInputSerializer,
    CrearPedidoInputSerializer,
    FacturarPedidoInputSerializer,
    PedidoWebSerializer,
    RechazarCancelarPedidoInputSerializer,
)
from .services import OrderError, OrderService


class PedidoWebViewSet(viewsets.ReadOnlyModelViewSet):
    """Lectura: los pedidos se crean exclusivamente vía OrderService.crear_pedido()."""

    queryset = PedidoWeb.objects.select_related(
        "empresa", "sucursal", "cliente", "portal_user", "lista_precio", "cupon", "deposito_reserva", "documento_venta",
    ).prefetch_related("items", "historial_estados")
    serializer_class = PedidoWebSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["estado", "cliente"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_superuser:
            qs = qs.filter(empresa=user.empresa)
        return qs


class CrearPedidoWebView(APIView):
    """POST /api/orders/pedidos/crear/ -- crea el pedido, valida y reserva stock automáticamente."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CrearPedidoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        empresa = get_object_or_404(Empresa, pk=data["empresa"])
        sucursal = get_object_or_404(Sucursal, pk=data["sucursal"])
        cliente = get_object_or_404(Cliente, pk=data["cliente"])
        lista_precio = get_object_or_404(ListaPrecio, pk=data["lista_precio"])
        deposito_reserva = get_object_or_404(Deposito, pk=data["deposito_reserva"])

        try:
            pedido = OrderService.crear_pedido(
                empresa=empresa, sucursal=sucursal, cliente=cliente, lista_precio=lista_precio,
                deposito_reserva=deposito_reserva, items_data=data["items"],
                cupon_code=data.get("cupon_code") or None, observaciones=data.get("observaciones", ""),
            )
        except OrderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PedidoWebSerializer(pedido).data, status=status.HTTP_201_CREATED)


def _get_scoped_pedido(request, pedido_id):
    qs = PedidoWeb.objects.all() if request.user.is_superuser else PedidoWeb.objects.filter(empresa=request.user.empresa)
    return get_object_or_404(qs, pk=pedido_id)


class AprobarPedidoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pedido_id):
        serializer = AccionPedidoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pedido = _get_scoped_pedido(request, pedido_id)
        try:
            pedido = OrderService.aprobar_pedido(pedido, request.user, nota=serializer.validated_data.get("nota", ""))
        except OrderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PedidoWebSerializer(pedido).data)


class RechazarPedidoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pedido_id):
        serializer = RechazarCancelarPedidoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pedido = _get_scoped_pedido(request, pedido_id)
        try:
            pedido = OrderService.rechazar_pedido(pedido, serializer.validated_data["motivo"], request.user)
        except OrderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PedidoWebSerializer(pedido).data)


class CancelarPedidoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pedido_id):
        serializer = RechazarCancelarPedidoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pedido = _get_scoped_pedido(request, pedido_id)
        try:
            pedido = OrderService.cancelar_pedido(pedido, serializer.validated_data["motivo"], request.user)
        except OrderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PedidoWebSerializer(pedido).data)


class MarcarEnPickingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pedido_id):
        serializer = AccionPedidoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pedido = _get_scoped_pedido(request, pedido_id)
        try:
            pedido = OrderService.marcar_en_picking(pedido, request.user, nota=serializer.validated_data.get("nota", ""))
        except OrderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PedidoWebSerializer(pedido).data)


class FacturarPedidoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pedido_id):
        serializer = FacturarPedidoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        pedido = _get_scoped_pedido(request, pedido_id)
        punto_venta = get_object_or_404(PuntoVenta, pk=data["punto_venta"])
        try:
            pedido = OrderService.facturar_pedido(
                pedido, punto_venta=punto_venta, usuario=request.user, condicion_venta=data["condicion_venta"]
            )
        except OrderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PedidoWebSerializer(pedido).data)


class MarcarDespachadoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pedido_id):
        serializer = AccionPedidoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pedido = _get_scoped_pedido(request, pedido_id)
        try:
            pedido = OrderService.marcar_despachado(pedido, request.user, nota=serializer.validated_data.get("nota", ""))
        except OrderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PedidoWebSerializer(pedido).data)


class MarcarEntregadoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pedido_id):
        serializer = AccionPedidoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pedido = _get_scoped_pedido(request, pedido_id)
        try:
            pedido = OrderService.marcar_entregado(pedido, request.user, nota=serializer.validated_data.get("nota", ""))
        except OrderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PedidoWebSerializer(pedido).data)
