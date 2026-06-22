from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import Deposito, Empresa, PuntoVenta, Sucursal
from apps.customers.models import Cliente

from .models import DocumentoVenta
from .serializers import (
    AnularDocumentoInputSerializer,
    ConvertirPresupuestoInputSerializer,
    DocumentoVentaSerializer,
    EmitirDocumentoInputSerializer,
)
from .services import BillingError, BillingService


class DocumentoVentaViewSet(viewsets.ReadOnlyModelViewSet):
    """Lectura: los documentos se crean exclusivamente vía BillingService.emitir_documento()."""

    queryset = DocumentoVenta.objects.select_related(
        "empresa", "sucursal", "punto_venta", "cliente", "moneda", "deposito_salida", "usuario", "documento_referencia",
    ).prefetch_related("items")
    serializer_class = DocumentoVentaSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["tipo_documento", "estado", "cliente", "condicion_venta"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_superuser:
            qs = qs.filter(empresa=user.empresa)
        return qs


class EmitirDocumentoVentaView(APIView):
    """POST /api/billing/documentos/emitir/ -- emite Factura/NC/ND/Presupuesto/Remisión."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = EmitirDocumentoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        empresa = get_object_or_404(Empresa, pk=data["empresa"])
        sucursal = get_object_or_404(Sucursal, pk=data["sucursal"])
        punto_venta = get_object_or_404(PuntoVenta, pk=data["punto_venta"])
        cliente = get_object_or_404(Cliente, pk=data["cliente"])
        deposito_salida = None
        if data.get("deposito_salida"):
            deposito_salida = get_object_or_404(Deposito, pk=data["deposito_salida"])
        documento_referencia = None
        if data.get("documento_referencia"):
            documento_referencia = get_object_or_404(DocumentoVenta, pk=data["documento_referencia"])

        try:
            documento = BillingService.emitir_documento(
                empresa=empresa, sucursal=sucursal, punto_venta=punto_venta,
                tipo_documento=data["tipo_documento"], cliente=cliente, moneda_code=data["moneda_code"],
                items_data=data["items"], usuario=request.user, condicion_venta=data["condicion_venta"],
                fecha_emision=data.get("fecha_emision"), fecha_vencimiento=data.get("fecha_vencimiento"),
                documento_referencia=documento_referencia, afecta_inventario=data["afecta_inventario"],
                deposito_salida=deposito_salida, observaciones=data.get("observaciones", ""),
            )
        except BillingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(DocumentoVentaSerializer(documento).data, status=status.HTTP_201_CREATED)


class AnularDocumentoVentaView(APIView):
    """POST /api/billing/documentos/<id>/anular/ {"motivo": "..."}"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, documento_id):
        serializer = AnularDocumentoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        qs = DocumentoVenta.objects.all() if request.user.is_superuser else DocumentoVenta.objects.filter(empresa=request.user.empresa)
        documento = get_object_or_404(qs, pk=documento_id)

        try:
            documento = BillingService.anular_documento(documento, serializer.validated_data["motivo"], request.user)
        except BillingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(DocumentoVentaSerializer(documento).data)


class ConvertirPresupuestoView(APIView):
    """POST /api/billing/documentos/<id>/convertir-a-factura/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, documento_id):
        serializer = ConvertirPresupuestoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        qs = DocumentoVenta.objects.all() if request.user.is_superuser else DocumentoVenta.objects.filter(empresa=request.user.empresa)
        presupuesto = get_object_or_404(qs, pk=documento_id)
        punto_venta = get_object_or_404(PuntoVenta, pk=data["punto_venta"])
        deposito_salida = None
        if data.get("deposito_salida"):
            deposito_salida = get_object_or_404(Deposito, pk=data["deposito_salida"])

        try:
            factura = BillingService.convertir_presupuesto_a_factura(
                presupuesto, punto_venta=punto_venta, usuario=request.user,
                afecta_inventario=data["afecta_inventario"], deposito_salida=deposito_salida,
                condicion_venta=data["condicion_venta"],
            )
        except BillingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(DocumentoVentaSerializer(factura).data, status=status.HTTP_201_CREATED)


class DesgloseImpuestosView(APIView):
    """GET /api/billing/documentos/<id>/desglose-impuestos/"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, documento_id):
        qs = DocumentoVenta.objects.all() if request.user.is_superuser else DocumentoVenta.objects.filter(empresa=request.user.empresa)
        documento = get_object_or_404(qs, pk=documento_id)
        return Response(documento.desglose_impuestos())
