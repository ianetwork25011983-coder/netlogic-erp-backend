"""
Módulo 8 - Gestión de Pedidos Web.

Flujo: BORRADOR (carrito) -> PENDIENTE_VALIDACION -> VALIDADO (con stock
reservado vía InventoryService.reservar_stock) -> APROBADO -> EN_PICKING
-> FACTURADO (acá se consume la reserva y se genera la salida real de
stock vía BillingService) -> DESPACHADO -> ENTREGADO. RECHAZADO/CANCELADO
liberan cualquier reserva activa.

`HistorialEstadoPedido` registra cada transición para dar "seguimiento en
tiempo real" sin necesitar todavía un consumer de Channels (se puede
agregar después sin tocar este modelo).
"""
from django.core.exceptions import ValidationError
from django.db import models


class PedidoWeb(models.Model):
    PRIORIDAD_NORMAL = "NORMAL"
    PRIORIDAD_ALTA = "ALTA"
    PRIORIDAD_URGENTE = "URGENTE"
    PRIORIDAD_CHOICES = [
        (PRIORIDAD_NORMAL, "Normal"),
        (PRIORIDAD_ALTA, "Alta"),
        (PRIORIDAD_URGENTE, "Urgente"),
    ]

    ESTADO_BORRADOR = "BORRADOR"
    ESTADO_PENDIENTE_VALIDACION = "PENDIENTE_VALIDACION"
    ESTADO_VALIDADO = "VALIDADO"
    ESTADO_RECHAZADO = "RECHAZADO"
    ESTADO_APROBADO = "APROBADO"
    ESTADO_EN_PICKING = "EN_PICKING"
    ESTADO_FACTURADO = "FACTURADO"
    ESTADO_DESPACHADO = "DESPACHADO"
    ESTADO_ENTREGADO = "ENTREGADO"
    ESTADO_CANCELADO = "CANCELADO"
    ESTADO_CHOICES = [
        (ESTADO_BORRADOR, "Borrador (carrito)"),
        (ESTADO_PENDIENTE_VALIDACION, "Pendiente de validación"),
        (ESTADO_VALIDADO, "Validado (stock reservado)"),
        (ESTADO_RECHAZADO, "Rechazado"),
        (ESTADO_APROBADO, "Aprobado"),
        (ESTADO_EN_PICKING, "En picking"),
        (ESTADO_FACTURADO, "Facturado"),
        (ESTADO_DESPACHADO, "Despachado"),
        (ESTADO_ENTREGADO, "Entregado"),
        (ESTADO_CANCELADO, "Cancelado"),
    ]
    ESTADOS_CON_RESERVA_ACTIVA = (ESTADO_VALIDADO, ESTADO_APROBADO, ESTADO_EN_PICKING)

    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="pedidos_web")
    sucursal = models.ForeignKey("companies.Sucursal", on_delete=models.CASCADE, related_name="pedidos_web")
    numero = models.CharField(max_length=30, unique=True)
    cliente = models.ForeignKey("customers.Cliente", on_delete=models.PROTECT, related_name="pedidos_web")
    portal_user = models.ForeignKey(
        "customer_portal.PortalUser", on_delete=models.SET_NULL, related_name="pedidos_creados", null=True, blank=True,
        help_text="Quién creó el pedido desde el portal (nulo si lo creó un usuario interno)",
    )

    lista_precio = models.ForeignKey("pricing.ListaPrecio", on_delete=models.PROTECT, related_name="pedidos_web")
    cupon = models.ForeignKey("pricing.Cupon", on_delete=models.SET_NULL, related_name="pedidos_web", null=True, blank=True)
    deposito_reserva = models.ForeignKey("companies.Deposito", on_delete=models.PROTECT, related_name="pedidos_web")

    estado = models.CharField(max_length=22, choices=ESTADO_CHOICES, default=ESTADO_BORRADOR)
    prioridad = models.CharField(
        max_length=10, choices=PRIORIDAD_CHOICES, default=PRIORIDAD_NORMAL,
        help_text="Puede asignarla el Módulo 16 (motor de reglas) automáticamente, ej. para clientes VIP",
    )
    motivo_rechazo = models.CharField(max_length=255, blank=True)

    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    descuento_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    documento_venta = models.ForeignKey(
        "billing.DocumentoVenta", on_delete=models.SET_NULL, related_name="pedido_origen", null=True, blank=True
    )

    observaciones = models.TextField(blank=True)
    fecha_pedido = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pedido Web"
        verbose_name_plural = "Pedidos Web"
        ordering = ["-fecha_pedido"]

    def __str__(self):
        return f"Pedido {self.numero} - {self.cliente}"


class PedidoWebItem(models.Model):
    pedido = models.ForeignKey(PedidoWeb, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey("products.Producto", on_delete=models.PROTECT, related_name="+")
    cantidad = models.DecimalField(max_digits=18, decimal_places=4)
    precio_unitario = models.DecimalField(max_digits=18, decimal_places=6)
    descuento_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    subtotal_linea = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Ítem de Pedido Web"
        verbose_name_plural = "Ítems de Pedido Web"

    def __str__(self):
        return f"{self.pedido.numero} - {self.producto.codigo} x{self.cantidad}"

    def clean(self):
        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError("La cantidad debe ser mayor a cero.")


class HistorialEstadoPedido(models.Model):
    """Bitácora de transiciones de estado, para seguimiento (polling-friendly; Channels es un follow-up)."""

    pedido = models.ForeignKey(PedidoWeb, on_delete=models.CASCADE, related_name="historial_estados")
    estado_anterior = models.CharField(max_length=22, blank=True)
    estado_nuevo = models.CharField(max_length=22)
    usuario = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, related_name="+", null=True, blank=True)
    nota = models.CharField(max_length=255, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Historial de Estado de Pedido"
        verbose_name_plural = "Historial de Estados de Pedido"
        ordering = ["fecha"]

    def __str__(self):
        return f"{self.pedido.numero}: {self.estado_anterior} -> {self.estado_nuevo}"
