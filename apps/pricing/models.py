"""
Precios, promociones y cupones (Módulo 8 - Gestión de Pedidos Web).

`Producto.precio` sigue existiendo como precio de lista por defecto
(fallback), pero `ListaPrecio`/`PrecioProducto` permiten tener varias
listas (ej. lista mayorista, lista minorista, lista por cliente VIP).
`OrderService` resuelve el precio de cada línea consultando primero la
lista indicada y, si el producto no tiene precio ahí, usa
`Producto.precio`.
"""
from django.core.exceptions import ValidationError
from django.db import models


class ListaPrecio(models.Model):
    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="listas_precio")
    nombre = models.CharField(max_length=100)
    moneda = models.ForeignKey("currencies.Currency", on_delete=models.PROTECT, related_name="listas_precio")
    es_default = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lista de Precios"
        verbose_name_plural = "Listas de Precios"
        ordering = ["empresa", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["empresa", "nombre"], name="unique_lista_precio_por_empresa")
        ]

    def __str__(self):
        return f"{self.nombre} ({self.moneda.code})"

    def clean(self):
        if self.es_default:
            qs = ListaPrecio.objects.filter(empresa=self.empresa, es_default=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError("Ya existe una lista de precios marcada como predeterminada para esta empresa.")

    @classmethod
    def get_default(cls, empresa):
        return cls.objects.filter(empresa=empresa, es_default=True, active=True).first()


class PrecioProducto(models.Model):
    lista_precio = models.ForeignKey(ListaPrecio, on_delete=models.CASCADE, related_name="precios")
    producto = models.ForeignKey("products.Producto", on_delete=models.CASCADE, related_name="precios_lista")
    precio = models.DecimalField(max_digits=18, decimal_places=6)

    class Meta:
        verbose_name = "Precio de Producto"
        verbose_name_plural = "Precios de Producto"
        constraints = [
            models.UniqueConstraint(fields=["lista_precio", "producto"], name="unique_precio_por_lista_y_producto")
        ]

    def __str__(self):
        return f"{self.producto.codigo} @ {self.lista_precio.nombre} = {self.precio}"


class Promocion(models.Model):
    """Descuento automático aplicado a productos o a una categoría completa, dentro de una vigencia."""

    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="promociones")
    nombre = models.CharField(max_length=150)
    descuento_porcentaje = models.DecimalField(max_digits=5, decimal_places=2)
    productos = models.ManyToManyField("products.Producto", blank=True, related_name="promociones")
    categoria = models.ForeignKey(
        "products.Categoria", on_delete=models.CASCADE, related_name="promociones", null=True, blank=True
    )
    vigencia_desde = models.DateField()
    vigencia_hasta = models.DateField()
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Promoción"
        verbose_name_plural = "Promociones"
        ordering = ["-vigencia_desde"]

    def __str__(self):
        return f"{self.nombre} (-{self.descuento_porcentaje}%)"

    def aplica_a(self, producto) -> bool:
        if self.categoria_id and producto.categoria_id == self.categoria_id:
            return True
        return self.productos.filter(pk=producto.pk).exists()

    def vigente(self, fecha) -> bool:
        return self.active and self.vigencia_desde <= fecha <= self.vigencia_hasta


class Cupon(models.Model):
    TIPO_PORCENTAJE = "PORCENTAJE"
    TIPO_MONTO_FIJO = "MONTO_FIJO"
    TIPO_CHOICES = [
        (TIPO_PORCENTAJE, "Descuento porcentual"),
        (TIPO_MONTO_FIJO, "Monto fijo"),
    ]

    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="cupones")
    codigo = models.CharField(max_length=30)
    tipo_descuento = models.CharField(max_length=12, choices=TIPO_CHOICES, default=TIPO_PORCENTAJE)
    valor = models.DecimalField(max_digits=18, decimal_places=2, help_text="Porcentaje (0-100) o monto fijo en la moneda del pedido")
    monto_minimo_compra = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    vigencia_desde = models.DateField()
    vigencia_hasta = models.DateField()
    usos_maximos = models.PositiveIntegerField(null=True, blank=True, help_text="Vacío = ilimitado")
    usos_actuales = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Cupón"
        verbose_name_plural = "Cupones"
        constraints = [
            models.UniqueConstraint(fields=["empresa", "codigo"], name="unique_cupon_codigo_por_empresa")
        ]

    def __str__(self):
        return self.codigo

    def es_valido(self, fecha, monto_compra) -> tuple:
        """Devuelve (es_valido: bool, motivo: str)."""
        if not self.active:
            return False, "El cupón no está activo."
        if not (self.vigencia_desde <= fecha <= self.vigencia_hasta):
            return False, "El cupón está fuera de su período de vigencia."
        if self.usos_maximos is not None and self.usos_actuales >= self.usos_maximos:
            return False, "El cupón alcanzó su límite de usos."
        if monto_compra < self.monto_minimo_compra:
            return False, f"La compra no alcanza el mínimo requerido ({self.monto_minimo_compra})."
        return True, ""

    def calcular_descuento(self, monto_compra):
        if self.tipo_descuento == self.TIPO_PORCENTAJE:
            return monto_compra * self.valor / 100
        return min(self.valor, monto_compra)
