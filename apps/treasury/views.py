from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AperturaCaja, Banco, Caja, CierreCaja, CuentaBancaria, MovimientoBancario, MovimientoCaja
from .serializers import (
    AbrirCajaInputSerializer,
    AperturaCajaSerializer,
    BancoSerializer,
    CajaSerializer,
    CerrarCajaInputSerializer,
    CierreCajaSerializer,
    CobroFacturaInputSerializer,
    CuentaBancariaSerializer,
    MovimientoBancarioInputSerializer,
    MovimientoBancarioSerializer,
    MovimientoCajaSerializer,
    PagoProveedorInputSerializer,
    RegistrarMovimientoInputSerializer,
)
from .services import TreasuryError, TreasuryService


class ScopedToEmpresaMixin:
    empresa_lookup = "empresa"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(**{self.empresa_lookup: user.empresa})


class CajaViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = Caja.objects.select_related("empresa", "sucursal", "punto_venta")
    serializer_class = CajaSerializer
    permission_classes = [permissions.IsAuthenticated]


class AperturaCajaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AperturaCaja.objects.select_related("caja", "usuario", "moneda").prefetch_related("movimientos")
    serializer_class = AperturaCajaSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["caja", "estado"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_superuser:
            qs = qs.filter(caja__empresa=user.empresa)
        return qs


class AbrirCajaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.currencies.models import Currency

        serializer = AbrirCajaInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        caja = get_object_or_404(Caja, pk=data["caja_id"])
        moneda = get_object_or_404(Currency, pk=data["moneda_id"])

        try:
            apertura = TreasuryService.abrir_caja(
                caja, request.user, data["monto_inicial"], moneda, observaciones=data.get("observaciones", "")
            )
        except TreasuryError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(AperturaCajaSerializer(apertura).data, status=status.HTTP_201_CREATED)


class CerrarCajaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, apertura_id):
        serializer = CerrarCajaInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        apertura = get_object_or_404(AperturaCaja, pk=apertura_id)
        try:
            cierre = TreasuryService.cerrar_caja(
                apertura, data["monto_contado_efectivo"], request.user, observaciones=data.get("observaciones", "")
            )
        except TreasuryError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(CierreCajaSerializer(cierre).data, status=status.HTTP_201_CREATED)


class RegistrarMovimientoCajaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.currencies.models import Currency

        serializer = RegistrarMovimientoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        apertura = get_object_or_404(AperturaCaja, pk=data["apertura_caja_id"])
        moneda = get_object_or_404(Currency, pk=data["moneda_id"])

        try:
            movimiento = TreasuryService.registrar_movimiento(
                apertura, tipo=data["tipo"], concepto=data["concepto"], medio_pago=data["medio_pago"],
                monto=data["monto"], moneda=moneda, usuario=request.user, observaciones=data.get("observaciones", ""),
            )
        except TreasuryError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(MovimientoCajaSerializer(movimiento).data, status=status.HTTP_201_CREATED)


class CobroFacturaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.billing.models import DocumentoVenta

        serializer = CobroFacturaInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        apertura = get_object_or_404(AperturaCaja, pk=data["apertura_caja_id"])
        documento = get_object_or_404(DocumentoVenta, pk=data["documento_venta_id"])

        try:
            movimiento = TreasuryService.registrar_cobro_factura(
                apertura, documento, data["monto"], data["medio_pago"], request.user,
                observaciones=data.get("observaciones", ""),
            )
        except TreasuryError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(MovimientoCajaSerializer(movimiento).data, status=status.HTTP_201_CREATED)


class PagoProveedorView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.purchases.models import FacturaProveedor

        serializer = PagoProveedorInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        apertura = get_object_or_404(AperturaCaja, pk=data["apertura_caja_id"])
        factura = get_object_or_404(FacturaProveedor, pk=data["factura_proveedor_id"])

        try:
            movimiento = TreasuryService.registrar_pago_proveedor(
                apertura, factura, data["monto"], data["medio_pago"], request.user,
                observaciones=data.get("observaciones", ""),
            )
        except TreasuryError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(MovimientoCajaSerializer(movimiento).data, status=status.HTTP_201_CREATED)


class BancoViewSet(viewsets.ModelViewSet):
    queryset = Banco.objects.all()
    serializer_class = BancoSerializer
    permission_classes = [permissions.IsAuthenticated]


class CuentaBancariaViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = CuentaBancaria.objects.select_related("empresa", "banco", "moneda")
    serializer_class = CuentaBancariaSerializer
    permission_classes = [permissions.IsAuthenticated]


class MovimientoBancarioViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MovimientoBancario.objects.select_related("cuenta_bancaria")
    serializer_class = MovimientoBancarioSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["cuenta_bancaria", "tipo"]


class RegistrarMovimientoBancarioView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = MovimientoBancarioInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cuenta = get_object_or_404(CuentaBancaria, pk=data["cuenta_bancaria_id"])

        try:
            movimiento = TreasuryService.registrar_movimiento_bancario(
                cuenta, tipo=data["tipo"], monto=data["monto"], usuario=request.user,
                referencia=data.get("referencia", ""), observaciones=data.get("observaciones", ""),
            )
        except TreasuryError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(MovimientoBancarioSerializer(movimiento).data, status=status.HTTP_201_CREATED)
