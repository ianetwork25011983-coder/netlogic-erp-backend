from rest_framework import permissions, viewsets

from .models import Cupon, ListaPrecio, Promocion
from .serializers import CuponSerializer, ListaPrecioSerializer, PromocionSerializer


class ScopedToEmpresaMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(empresa=user.empresa)


class ListaPrecioViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = ListaPrecio.objects.select_related("empresa", "moneda").prefetch_related("precios")
    serializer_class = ListaPrecioSerializer
    permission_classes = [permissions.IsAuthenticated]


class PromocionViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = Promocion.objects.select_related("empresa", "categoria").prefetch_related("productos")
    serializer_class = PromocionSerializer
    permission_classes = [permissions.IsAuthenticated]


class CuponViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = Cupon.objects.select_related("empresa")
    serializer_class = CuponSerializer
    permission_classes = [permissions.IsAuthenticated]
