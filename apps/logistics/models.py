"""
Módulo 12 - Logística.

Conecta con el flujo de `PedidoWeb` (Módulo 8): `OrdenPicking` da el
detalle operativo (quién pickeó qué, de qué ubicación) detrás del
estado `PedidoWeb.EN_PICKING`, y `Despacho`/`DespachoDocumento` dan el
detalle detrás de `DESPACHADO`/`ENTREGADO`. Las transiciones de estado
del pedido en sí las sigue manejando `OrderService` (Módulo 8); este
módulo aporta el detalle operativo y, cuando corresponde, dispara esas
transiciones para no duplicar la máquina de estados.
"""
from django.core.exceptions import ValidationError
from django.db import models


class Transportista(models.Model):
    TIPO_PROPIO = "PROPIO"
    TIPO_TERCERIZADO = "TERCERIZADO"
    TIPO_CHOICES = [(TIPO_PROPIO, "Flota propia"), (TIPO_TERCERIZADO, "Tercerizado")]

    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="transportistas")
    razon_social = models.CharField(max_length=200)
    ruc = models.CharField(max_length=20, blank=True)
    tipo = models.CharField(max_length=12, choices=TIPO_CHOICES, default=TIPO_PROPIO)
    telefono = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Transportista"
        verbose_name_plural = "Transportistas"
        ordering = ["razon_social"]

    def __str__(self):
        return self.razon_social


class Vehiculo(models.Model):
    transportista = models.ForeignKey(Transportista, on_delete=models.CASCADE, related_name="vehiculos")
    placa = models.CharField(max_length=15)
    marca = models.CharField(max_length=50, blank=True)
    modelo = models.CharField(max_length=50, blank=True)
    capacidad_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    capacidad_m3 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Vehículo"
        verbose_name_plural = "Vehículos"
        constraints = [
            models.UniqueConstraint(fields=["transportista", "placa"], name="unique_vehiculo_placa_por_transportista")
        ]

    def __str__(self):
        return f"{self.placa} ({self.transportista})"


class Ruta(models.Model):
    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="rutas")
    nombre = models.CharField(max_length=100)
    zona = models.CharField(max_length=150, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Ruta"
        verbose_name_plural = "Rutas"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class OrdenPicking(models.Model):
    ESTADO_PENDIENTE = "PENDIENTE"
    ESTADO_EN_PROCESO = "EN_PROCESO"
    ESTADO_COMPLETADO = "COMPLETADO"
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_EN_PROCESO, "En proceso"),
        (ESTADO_COMPLETADO, "Completado"),
    ]

    pedido_web = models.OneToOneField(
        "orders.PedidoWeb", on_delete=models.CASCADE, related_name="orden_picking"
    )
    deposito = models.ForeignKey("companies.Deposito", on_delete=models.PROTECT, related_name="ordenes_picking")
    usuario_asignado = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="ordenes_picking_asignadas", null=True, blank=True
    )
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE)
    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Orden de Picking"
        verbose_name_plural = "Órdenes de Picking"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Picking {self.pedido_web.numero} - {self.estado}"


class OrdenPickingItem(models.Model):
    orden_picking = models.ForeignKey(OrdenPicking, on_delete=models.CASCADE, related_name="items")
    pedido_web_item = models.ForeignKey("orders.PedidoWebItem", on_delete=models.PROTECT, related_name="+")
    cantidad_pickeada = models.DecimalField(max_digits=18, decimal_places=4)
    ubicacion = models.ForeignKey(
        "inventory.Ubicacion", on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )

    class Meta:
        verbose_name = "Ítem de Picking"
        verbose_name_plural = "Ítems de Picking"

    def __str__(self):
        return f"{self.orden_picking} - {self.pedido_web_item.producto.codigo} x{self.cantidad_pickeada}"

    def clean(self):
        if self.cantidad_pickeada is not None and self.cantidad_pickeada <= 0:
            raise ValidationError("La cantidad pickeada debe ser mayor a cero.")


class OrdenPacking(models.Model):
    orden_picking = models.OneToOneField(OrdenPicking, on_delete=models.CASCADE, related_name="packing")
    cantidad_bultos = models.PositiveIntegerField(default=1)
    peso_total_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    volumen_total_m3 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    usuario = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, related_name="+", null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Orden de Packing"
        verbose_name_plural = "Órdenes de Packing"

    def __str__(self):
        return f"Packing {self.orden_picking.pedido_web.numero} - {self.cantidad_bultos} bultos"


class Despacho(models.Model):
    ESTADO_PENDIENTE = "PENDIENTE"
    ESTADO_EN_RUTA = "EN_RUTA"
    ESTADO_ENTREGADO = "ENTREGADO"
    ESTADO_PARCIAL = "PARCIAL"
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_EN_RUTA, "En ruta"),
        (ESTADO_ENTREGADO, "Entregado"),
        (ESTADO_PARCIAL, "Entregado parcialmente"),
    ]

    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="despachos")
    numero = models.CharField(max_length=30, unique=True)
    transportista = models.ForeignKey(Transportista, on_delete=models.PROTECT, related_name="despachos")
    vehiculo = models.ForeignKey(Vehiculo, on_delete=models.SET_NULL, related_name="despachos", null=True, blank=True)
    ruta = models.ForeignKey(Ruta, on_delete=models.SET_NULL, related_name="despachos", null=True, blank=True)
    conductor_nombre = models.CharField(max_length=150, blank=True)
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE)
    usuario = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="despachos_creados")
    observaciones = models.TextField(blank=True)
    fecha_despacho = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Despacho"
        verbose_name_plural = "Despachos"
        ordering = ["-fecha_despacho"]

    def __str__(self):
        return f"Despacho {self.numero} - {self.transportista}"


class DespachoDocumento(models.Model):
    ESTADO_PENDIENTE = "PENDIENTE"
    ESTADO_ENTREGADO = "ENTREGADO"
    ESTADO_FALLIDO = "FALLIDO"
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_ENTREGADO, "Entregado"),
        (ESTADO_FALLIDO, "Entrega fallida"),
    ]

    despacho = models.ForeignKey(Despacho, on_delete=models.CASCADE, related_name="documentos")
    documento_venta = models.ForeignKey(
        "billing.DocumentoVenta", on_delete=models.PROTECT, related_name="despachos"
    )
    orden_entrega = models.PositiveSmallIntegerField(default=1, help_text="Orden de visita dentro de la ruta")
    direccion_entrega = models.CharField(max_length=255, blank=True)
    estado_entrega = models.CharField(max_length=12, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE)
    fecha_entrega_real = models.DateTimeField(null=True, blank=True)
    firma_recibido = models.CharField(max_length=150, blank=True, help_text="Nombre de quién recibió la mercadería")
    observaciones = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Documento en Despacho"
        verbose_name_plural = "Documentos en Despacho"
        ordering = ["despacho", "orden_entrega"]
        constraints = [
            models.UniqueConstraint(fields=["despacho", "documento_venta"], name="unique_documento_por_despacho")
        ]

    def __str__(self):
        return f"{self.despacho.numero} - {self.documento_venta.numero}"
