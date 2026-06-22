from rest_framework import permissions, viewsets

from .models import Deposito, Empresa, PuntoVenta, Sucursal
from .serializers import (
    DepositoSerializer,
    EmpresaSerializer,
    PuntoVentaSerializer,
    SucursalSerializer,
)


class ScopedToEmpresaMixin:
    """Filtra automáticamente el queryset a la empresa del usuario, salvo superusuario."""

    empresa_lookup = "empresa"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(**{self.empresa_lookup: user.empresa})


class EmpresaViewSet(viewsets.ModelViewSet):
    queryset = Empresa.objects.select_related("moneda_default").all()
    serializer_class = EmpresaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(pk=user.empresa_id)


class SucursalViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = Sucursal.objects.select_related("empresa").prefetch_related("depositos", "puntos_venta")
    serializer_class = SucursalSerializer
    permission_classes = [permissions.IsAuthenticated]


class DepositoViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = Deposito.objects.select_related("sucursal", "sucursal__empresa")
    serializer_class = DepositoSerializer
    permission_classes = [permissions.IsAuthenticated]
    empresa_lookup = "sucursal__empresa"


class PuntoVentaViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = PuntoVenta.objects.select_related("sucursal", "sucursal__empresa")
    serializer_class = PuntoVentaSerializer
    permission_classes = [permissions.IsAuthenticated]
    empresa_lookup = "sucursal__empresa"
