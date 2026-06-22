from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import Deposito, Sucursal

from .models import Cotizacion, FacturaProveedor, OrdenCompra, RecepcionCompra, SolicitudCompra
from .serializers import (
    CotizacionSerializer,
    FacturaProveedorSerializer,
    OrdenCompraCreateSerializer,
    OrdenCompraSerializer,
    RecepcionCompraSerializer,
    RecibirOrdenInputSerializer,
    SolicitudCompraSerializer,
)
from .services import PurchaseError, PurchaseService


class ScopedToEmpresaMixin:
    empresa_lookup = "empresa"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(**{self.empresa_lookup: user.empresa})


class SolicitudCompraViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = SolicitudCompra.objects.select_related("empresa", "sucursal", "solicitante").prefetch_related("items")
    serializer_class = SolicitudCompraSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(solicitante=self.request.user)


class CotizacionViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = Cotizacion.objects.select_related("empresa", "proveedor", "moneda", "solicitud").prefetch_related("items")
    serializer_class = CotizacionSerializer
    permission_classes = [permissions.IsAuthenticated]


class CompararCotizacionesView(APIView):
    """GET /api/purchases/solicitudes/<id>/comparar-cotizaciones/"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, solicitud_id):
        qs = SolicitudCompra.objects.all() if request.user.is_superuser else SolicitudCompra.objects.filter(empresa=request.user.empresa)
        solicitud = get_object_or_404(qs, pk=solicitud_id)
        return Response(PurchaseService.comparar_cotizaciones(solicitud))


class CrearOrdenDesdeCotizacionView(APIView):
    """POST /api/purchases/cotizaciones/<id>/crear-orden/ {"sucursal": <id>, "condiciones_pago": "..."}"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, cotizacion_id):
        qs = Cotizacion.objects.all() if request.user.is_superuser else Cotizacion.objects.filter(empresa=request.user.empresa)
        cotizacion = get_object_or_404(qs, pk=cotizacion_id)
        sucursal = get_object_or_404(Sucursal, pk=request.data.get("sucursal"))

        orden = PurchaseService.crear_orden_desde_cotizacion(
            cotizacion, sucursal, request.user, condiciones_pago=request.data.get("condiciones_pago", "")
        )
        return Response(OrdenCompraSerializer(orden).data, status=status.HTTP_201_CREATED)


class OrdenCompraViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = OrdenCompra.objects.select_related("empresa", "sucursal", "proveedor", "moneda", "usuario").prefetch_related("items")
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return OrdenCompraCreateSerializer
        return OrdenCompraSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        orden = serializer.save()
        # La respuesta se construye con el serializer de LECTURA (anidado
        # con subtotal/cantidad_pendiente), no con el de escritura, que
        # solo está pensado para validar el input.
        output = OrdenCompraSerializer(orden, context=self.get_serializer_context())
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)


class RecibirOrdenCompraView(APIView):
    """POST /api/purchases/ordenes/recibir/ -- registra una recepción de mercadería."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = RecibirOrdenInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        qs = OrdenCompra.objects.all() if request.user.is_superuser else OrdenCompra.objects.filter(empresa=request.user.empresa)
        orden = get_object_or_404(qs, pk=data["orden_compra"])
        deposito = get_object_or_404(Deposito, pk=data["deposito"])

        try:
            recepcion = PurchaseService.recibir_orden(
                orden_compra=orden, deposito=deposito, items_data=data["items"],
                usuario=request.user, observaciones=data.get("observaciones", ""),
            )
        except PurchaseError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(RecepcionCompraSerializer(recepcion).data, status=status.HTTP_201_CREATED)


class RecepcionCompraViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RecepcionCompra.objects.select_related("orden_compra", "deposito", "usuario").prefetch_related("items")
    serializer_class = RecepcionCompraSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_superuser:
            qs = qs.filter(orden_compra__empresa=user.empresa)
        return qs


class FacturaProveedorViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = FacturaProveedor.objects.select_related("empresa", "proveedor", "orden_compra", "moneda")
    serializer_class = FacturaProveedorSerializer
    permission_classes = [permissions.IsAuthenticated]


class HistorialProveedorView(APIView):
    """GET /api/purchases/proveedores/<id>/historial/"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, proveedor_id):
        from apps.suppliers.models import Proveedor

        qs = Proveedor.objects.all() if request.user.is_superuser else Proveedor.objects.filter(empresa=request.user.empresa)
        proveedor = get_object_or_404(qs, pk=proveedor_id)
        return Response(PurchaseService.historial_proveedor(proveedor))
