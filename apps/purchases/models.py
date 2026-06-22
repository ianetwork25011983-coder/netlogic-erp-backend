"""
Módulo 9 - Compras.

Flujo: SolicitudCompra -> Cotizacion (una o más, por proveedor, para
comparar) -> OrdenCompra (generada desde la cotización elegida) ->
RecepcionCompra (una o más, parcial o total; cada recepción descuenta
contra `InventoryService.registrar_entrada`) -> FacturaProveedor.

Ninguno de estos modelos escribe stock directamente: solo
`PurchaseService.recibir_orden()` llama a `InventoryService`, manteniendo
una sola fuente de verdad para el Kardex.
"""
from django.core.exceptions import ValidationError
from django.db import models


class SolicitudCompra(models.Model):
    ESTADO_BORRADOR = "BORRADOR"
    ESTADO_APROBADA = "APROBADA"
    ESTADO_RECHAZADA = "RECHAZADA"
    ESTADO_CONVERTIDA = "CONVERTIDA"
    ESTADO_CHOICES = [
        (ESTADO_BORRADOR, "Borrador"),
        (ESTADO_APROBADA, "Aprobada"),
        (ESTADO_RECHAZADA, "Rechazada"),
        (ESTADO_CONVERTIDA, "Convertida en Orden de Compra"),
    ]

    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="solicitudes_compra")
    sucursal = models.ForeignKey("companies.Sucursal", on_delete=models.CASCADE, related_name="solicitudes_compra")
    numero = models.CharField(max_length=30, unique=True)
    solicitante = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="solicitudes_compra")
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default=ESTADO_BORRADOR)
    observaciones = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Solicitud de Compra"
        verbose_name_plural = "Solicitudes de Compra"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Solicitud {self.numero}"


class SolicitudCompraItem(models.Model):
    solicitud = models.ForeignKey(SolicitudCompra, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey("products.Producto", on_delete=models.PROTECT, related_name="+")
    cantidad = models.DecimalField(max_digits=18, decimal_places=4)
    observacion = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Ítem de Solicitud de Compra"
        verbose_name_plural = "Ítems de Solicitud de Compra"

    def __str__(self):
        return f"{self.solicitud.numero} - {self.producto.codigo} x{self.cantidad}"


class Cotizacion(models.Model):
    """Cotización recibida de un proveedor, en respuesta a una solicitud (o ad-hoc)."""

    ESTADO_PENDIENTE = "PENDIENTE"
    ESTADO_RECIBIDA = "RECIBIDA"
    ESTADO_SELECCIONADA = "SELECCIONADA"
    ESTADO_DESCARTADA = "DESCARTADA"
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_RECIBIDA, "Recibida"),
        (ESTADO_SELECCIONADA, "Seleccionada"),
        (ESTADO_DESCARTADA, "Descartada"),
    ]

    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="cotizaciones")
    solicitud = models.ForeignKey(
        SolicitudCompra, on_delete=models.SET_NULL, related_name="cotizaciones", null=True, blank=True
    )
    proveedor = models.ForeignKey("suppliers.Proveedor", on_delete=models.PROTECT, related_name="cotizaciones")
    numero = models.CharField(max_length=30, blank=True, help_text="Número de cotización del proveedor, si tiene")
    moneda = models.ForeignKey("currencies.Currency", on_delete=models.PROTECT, related_name="cotizaciones")
    plazo_entrega_dias = models.PositiveSmallIntegerField(default=0)
    condiciones_pago = models.CharField(max_length=150, blank=True)
    vigencia_hasta = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cotización de Compra"
        verbose_name_plural = "Cotizaciones de Compra"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Cotización {self.proveedor} - {self.fecha:%Y-%m-%d}"

    @property
    def total(self):
        return sum((item.subtotal for item in self.items.all()), start=0)


class CotizacionItem(models.Model):
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey("products.Producto", on_delete=models.PROTECT, related_name="+")
    cantidad = models.DecimalField(max_digits=18, decimal_places=4)
    precio_unitario = models.DecimalField(max_digits=18, decimal_places=6)
    descuento_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Ítem de Cotización"
        verbose_name_plural = "Ítems de Cotización"

    def __str__(self):
        return f"{self.producto.codigo} x{self.cantidad} @ {self.precio_unitario}"

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario * (1 - self.descuento_porcentaje / 100)


class OrdenCompra(models.Model):
    ESTADO_BORRADOR = "BORRADOR"
    ESTADO_ENVIADA = "ENVIADA"
    ESTADO_CONFIRMADA = "CONFIRMADA"
    ESTADO_RECIBIDA_PARCIAL = "RECIBIDA_PARCIAL"
    ESTADO_RECIBIDA_TOTAL = "RECIBIDA_TOTAL"
    ESTADO_CANCELADA = "CANCELADA"
    ESTADO_CHOICES = [
        (ESTADO_BORRADOR, "Borrador"),
        (ESTADO_ENVIADA, "Enviada al proveedor"),
        (ESTADO_CONFIRMADA, "Confirmada por el proveedor"),
        (ESTADO_RECIBIDA_PARCIAL, "Recibida parcialmente"),
        (ESTADO_RECIBIDA_TOTAL, "Recibida totalmente"),
        (ESTADO_CANCELADA, "Cancelada"),
    ]

    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="ordenes_compra")
    sucursal = models.ForeignKey("companies.Sucursal", on_delete=models.CASCADE, related_name="ordenes_compra")
    proveedor = models.ForeignKey("suppliers.Proveedor", on_delete=models.PROTECT, related_name="ordenes_compra")
    cotizacion = models.ForeignKey(
        Cotizacion, on_delete=models.SET_NULL, related_name="ordenes_compra", null=True, blank=True
    )
    numero = models.CharField(max_length=30, unique=True)
    moneda = models.ForeignKey("currencies.Currency", on_delete=models.PROTECT, related_name="ordenes_compra")
    condiciones_pago = models.CharField(max_length=150, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_BORRADOR)
    observaciones = models.TextField(blank=True)
    usuario = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="ordenes_compra")
    fecha = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Orden de Compra"
        verbose_name_plural = "Órdenes de Compra"
        ordering = ["-fecha"]

    def __str__(self):
        return f"OC {self.numero} - {self.proveedor}"

    @property
    def total(self):
        return sum((item.subtotal for item in self.items.all()), start=0)

    @property
    def totalmente_recibida(self) -> bool:
        return all(item.cantidad_recibida >= item.cantidad for item in self.items.all())

    @property
    def parcialmente_recibida(self) -> bool:
        return any(item.cantidad_recibida > 0 for item in self.items.all()) and not self.totalmente_recibida


class OrdenCompraItem(models.Model):
    orden_compra = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey("products.Producto", on_delete=models.PROTECT, related_name="+")
    cantidad = models.DecimalField(max_digits=18, decimal_places=4)
    precio_unitario = models.DecimalField(max_digits=18, decimal_places=6)
    descuento_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cantidad_recibida = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    class Meta:
        verbose_name = "Ítem de Orden de Compra"
        verbose_name_plural = "Ítems de Orden de Compra"

    def __str__(self):
        return f"{self.orden_compra.numero} - {self.producto.codigo} x{self.cantidad}"

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario * (1 - self.descuento_porcentaje / 100)

    @property
    def cantidad_pendiente(self):
        return self.cantidad - self.cantidad_recibida

    def clean(self):
        if self.cantidad_recibida and self.cantidad_recibida > self.cantidad:
            raise ValidationError("La cantidad recibida no puede superar la cantidad pedida.")


class RecepcionCompra(models.Model):
    orden_compra = models.ForeignKey(OrdenCompra, on_delete=models.PROTECT, related_name="recepciones")
    deposito = models.ForeignKey("companies.Deposito", on_delete=models.PROTECT, related_name="recepciones_compra")
    numero = models.CharField(max_length=30, unique=True)
    usuario = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="recepciones_compra")
    observaciones = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Recepción de Compra"
        verbose_name_plural = "Recepciones de Compra"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Recepción {self.numero} (OC {self.orden_compra.numero})"


class RecepcionCompraItem(models.Model):
    recepcion = models.ForeignKey(RecepcionCompra, on_delete=models.CASCADE, related_name="items")
    orden_compra_item = models.ForeignKey(OrdenCompraItem, on_delete=models.PROTECT, related_name="recepciones")
    cantidad_recibida = models.DecimalField(max_digits=18, decimal_places=4)
    numero_lote = models.CharField(max_length=50, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    movimiento_inventario = models.ForeignKey(
        "inventory.MovimientoInventario", on_delete=models.PROTECT, related_name="+", null=True, blank=True
    )

    class Meta:
        verbose_name = "Ítem de Recepción"
        verbose_name_plural = "Ítems de Recepción"

    def __str__(self):
        return f"{self.recepcion.numero} - {self.orden_compra_item.producto.codigo} x{self.cantidad_recibida}"


class FacturaProveedor(models.Model):
    ESTADO_PENDIENTE = "PENDIENTE"
    ESTADO_PAGADA = "PAGADA"
    ESTADO_PAGADA_PARCIAL = "PAGADA_PARCIAL"
    ESTADO_ANULADA = "ANULADA"
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_PAGADA, "Pagada"),
        (ESTADO_PAGADA_PARCIAL, "Pagada parcialmente"),
        (ESTADO_ANULADA, "Anulada"),
    ]

    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="facturas_proveedor")
    proveedor = models.ForeignKey("suppliers.Proveedor", on_delete=models.PROTECT, related_name="facturas")
    orden_compra = models.ForeignKey(
        OrdenCompra, on_delete=models.SET_NULL, related_name="facturas_proveedor", null=True, blank=True
    )
    numero_factura = models.CharField(max_length=30)
    timbrado_proveedor = models.CharField(max_length=20, blank=True)
    moneda = models.ForeignKey("currencies.Currency", on_delete=models.PROTECT, related_name="facturas_proveedor")
    monto_total = models.DecimalField(max_digits=18, decimal_places=2)
    saldo_pendiente = models.DecimalField(max_digits=18, decimal_places=2)
    fecha_emision = models.DateField()
    fecha_vencimiento = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE)
    observaciones = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Factura de Proveedor"
        verbose_name_plural = "Facturas de Proveedor"
        ordering = ["-fecha_emision"]
        constraints = [
            models.UniqueConstraint(
                fields=["proveedor", "numero_factura"], name="unique_factura_proveedor_numero"
            )
        ]

    def __str__(self):
        return f"Factura {self.numero_factura} - {self.proveedor}"

    def save(self, *args, **kwargs):
        if self.saldo_pendiente is None:
            self.saldo_pendiente = self.monto_total
        super().save(*args, **kwargs)
