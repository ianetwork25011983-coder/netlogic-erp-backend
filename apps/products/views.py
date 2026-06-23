from rest_framework import filters, permissions, viewsets
from django_filters.rest_framework import DjangoFilterBackend

from .models import Categoria, Impuesto, Lote, Marca, Producto, ProductoComponente, Serie, UnidadMedida
from .serializers import (
    CategoriaSerializer,
    ImpuestoSerializer,
    LoteSerializer,
    MarcaSerializer,
    ProductoComponenteSerializer,
    ProductoDetailSerializer,
    ProductoListSerializer,
    SerieSerializer,
    UnidadMedidaSerializer,
)


class ScopedToEmpresaMixin:
    empresa_lookup = "empresa"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(**{self.empresa_lookup: user.empresa})


class MarcaViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = Marca.objects.select_related("empresa")
    serializer_class = MarcaSerializer
    permission_classes = [permissions.IsAuthenticated]


class CategoriaViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = Categoria.objects.select_related("empresa", "parent")
    serializer_class = CategoriaSerializer
    permission_classes = [permissions.IsAuthenticated]


class UnidadMedidaViewSet(viewsets.ModelViewSet):
    queryset = UnidadMedida.objects.all()
    serializer_class = UnidadMedidaSerializer
    permission_classes = [permissions.IsAuthenticated]


class ImpuestoViewSet(viewsets.ModelViewSet):
    queryset = Impuesto.objects.all()
    serializer_class = ImpuestoSerializer
    permission_classes = [permissions.IsAuthenticated]


class ProductoViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = Producto.objects.select_related(
        "empresa", "marca", "categoria", "proveedor_principal",
        "unidad_medida", "impuesto", "moneda_costo", "moneda_precio",
    ).prefetch_related("componentes", "lotes")
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["tipo", "marca", "categoria", "active"]
    search_fields = ["codigo", "nombre", "sku", "codigo_barras"]

    def get_serializer_class(self):
        if self.action == "list":
            return ProductoListSerializer
        return ProductoDetailSerializer


class ProductoComponenteViewSet(viewsets.ModelViewSet):
    queryset = ProductoComponente.objects.select_related("producto_padre", "producto_componente")
    serializer_class = ProductoComponenteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_superuser:
            qs = qs.filter(producto_padre__empresa=user.empresa)
        return qs


class LoteViewSet(viewsets.ModelViewSet):
    queryset = Lote.objects.select_related("producto", "proveedor")
    serializer_class = LoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_superuser:
            qs = qs.filter(producto__empresa=user.empresa)
        return qs


class SerieViewSet(viewsets.ModelViewSet):
    queryset = Serie.objects.select_related("producto", "lote", "deposito_actual")
    serializer_class = SerieSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_superuser:
            qs = qs.filter(producto__empresa=user.empresa)
        return qs
