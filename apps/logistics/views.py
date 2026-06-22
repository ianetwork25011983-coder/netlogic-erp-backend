from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Despacho, DespachoDocumento, OrdenPacking, OrdenPicking, Ruta, Transportista, Vehiculo
from .serializers import (
    CompletarPickingInputSerializer,
    CrearDespachoInputSerializer,
    CrearPackingInputSerializer,
    DespachoSerializer,
    IniciarPickingInputSerializer,
    OrdenPackingSerializer,
    OrdenPickingSerializer,
    RegistrarEntregaInputSerializer,
    RutaSerializer,
    TransportistaSerializer,
    VehiculoSerializer,
)
from .services import LogisticsError, LogisticsService


class ScopedToEmpresaMixin:
    empresa_lookup = "empresa"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(**{self.empresa_lookup: user.empresa})


class TransportistaViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = Transportista.objects.select_related("empresa")
    serializer_class = TransportistaSerializer
    permission_classes = [permissions.IsAuthenticated]


class VehiculoViewSet(viewsets.ModelViewSet):
    queryset = Vehiculo.objects.select_related("transportista")
    serializer_class = VehiculoSerializer
    permission_classes = [permissions.IsAuthenticated]


class RutaViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = Ruta.objects.select_related("empresa")
    serializer_class = RutaSerializer
    permission_classes = [permissions.IsAuthenticated]


class OrdenPickingViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OrdenPicking.objects.select_related("pedido_web", "deposito", "usuario_asignado").prefetch_related("items")
    serializer_class = OrdenPickingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["estado", "deposito"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_superuser:
            qs = qs.filter(pedido_web__empresa=user.empresa)
        return qs


class IniciarPickingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.companies.models import Deposito
        from apps.orders.models import PedidoWeb

        serializer = IniciarPickingInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        pedido = get_object_or_404(PedidoWeb, pk=data["pedido_web_id"])
        deposito = get_object_or_404(Deposito, pk=data["deposito_id"])
        usuario_asignado = None
        if data.get("usuario_asignado_id"):
            from apps.accounts.models import User

            usuario_asignado = get_object_or_404(User, pk=data["usuario_asignado_id"])

        try:
            orden = LogisticsService.iniciar_picking(pedido, deposito, usuario_asignado)
        except LogisticsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(OrdenPickingSerializer(orden).data, status=status.HTTP_201_CREATED)


class CompletarPickingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, orden_picking_id):
        serializer = CompletarPickingInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        orden = get_object_or_404(OrdenPicking, pk=orden_picking_id)
        try:
            orden = LogisticsService.completar_picking(orden, serializer.validated_data["items"], request.user)
        except LogisticsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(OrdenPickingSerializer(orden).data)


class CrearPackingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, orden_picking_id):
        serializer = CrearPackingInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        orden = get_object_or_404(OrdenPicking, pk=orden_picking_id)
        try:
            packing = LogisticsService.crear_packing(
                orden, cantidad_bultos=data["cantidad_bultos"], peso_total_kg=data.get("peso_total_kg"),
                volumen_total_m3=data.get("volumen_total_m3"), usuario=request.user,
            )
        except LogisticsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(OrdenPackingSerializer(packing).data, status=status.HTTP_201_CREATED)


class DespachoViewSet(ScopedToEmpresaMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Despacho.objects.select_related("empresa", "transportista", "vehiculo", "ruta", "usuario").prefetch_related("documentos")
    serializer_class = DespachoSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["estado", "transportista"]


class CrearDespachoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.billing.models import DocumentoVenta
        from apps.companies.models import Empresa

        serializer = CrearDespachoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        empresa = get_object_or_404(Empresa, pk=data["empresa_id"])
        transportista = get_object_or_404(Transportista, pk=data["transportista_id"])
        vehiculo = get_object_or_404(Vehiculo, pk=data["vehiculo_id"]) if data.get("vehiculo_id") else None
        ruta = get_object_or_404(Ruta, pk=data["ruta_id"]) if data.get("ruta_id") else None
        documentos = list(DocumentoVenta.objects.filter(pk__in=data["documentos_venta_ids"]))

        despacho = LogisticsService.crear_despacho(
            empresa, documentos, transportista, request.user, vehiculo=vehiculo, ruta=ruta,
            conductor_nombre=data.get("conductor_nombre", ""), observaciones=data.get("observaciones", ""),
        )
        return Response(DespachoSerializer(despacho).data, status=status.HTTP_201_CREATED)


class RegistrarEntregaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, despacho_documento_id):
        serializer = RegistrarEntregaInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        despacho_documento = get_object_or_404(DespachoDocumento, pk=despacho_documento_id)
        resultado = LogisticsService.registrar_entrega(
            despacho_documento, estado_entrega=data["estado_entrega"], usuario=request.user,
            firma_recibido=data.get("firma_recibido", ""), observaciones=data.get("observaciones", ""),
        )
        from .serializers import DespachoDocumentoSerializer

        return Response(DespachoDocumentoSerializer(resultado).data)
