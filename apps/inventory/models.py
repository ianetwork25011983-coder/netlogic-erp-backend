"""
Módulo 4 - Control Avanzado de Inventario.

Arquitectura de costeo:
- `MovimientoInventario` es la fuente de verdad inmutable (Kardex). Nunca
  se edita ni se borra un movimiento ya creado; un error se corrige con
  un movimiento de ajuste inverso, igual que en un libro contable.
- `StockBalance` es un saldo denormalizado (producto+depósito+lote) que
  se mantiene sincronizado transaccionalmente desde
  `apps.inventory.services.InventoryService` para poder leer "cuánto hay
  ahora" sin recorrer todo el Kardex en cada consulta.
- `CapaCosto` (cost layer) solo se usa para productos con método de
  costeo FIFO o LIFO: cada entrada de stock crea una capa con su propio
  costo unitario; las salidas consumen capas en orden (FIFO: más antigua
  primero, LIFO: más nueva primero). Para productos con método PROMEDIO
  no se crean capas: el costo promedio ponderado se recalcula directo en
  `StockBalance.costo_promedio_pyg`.
"""
from django.core.exceptions import ValidationError
from django.db import models


class Ubicacion(models.Model):
    """Ubicación física dentro de un depósito: rack / pasillo / estantería / nivel."""

    deposito = models.ForeignKey("companies.Deposito", on_delete=models.CASCADE, related_name="ubicaciones")
    codigo = models.CharField(max_length=20, help_text="Código compuesto, ej: A-01-03")
    rack = models.CharField(max_length=20, blank=True)
    pasillo = models.CharField(max_length=20, blank=True)
    estanteria = models.CharField(max_length=20, blank=True)
    nivel = models.CharField(max_length=20, blank=True)
    descripcion = models.CharField(max_length=150, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Ubicación"
        verbose_name_plural = "Ubicaciones"
        ordering = ["deposito", "codigo"]
        constraints = [
            models.UniqueConstraint(fields=["deposito", "codigo"], name="unique_ubicacion_codigo_por_deposito")
        ]

    def __str__(self):
        return f"{self.deposito} - {self.codigo}"


class StockBalance(models.Model):
    """Saldo actual (cantidad y costo) de un producto en un depósito, opcionalmente por lote."""

    producto = models.ForeignKey("products.Producto", on_delete=models.CASCADE, related_name="saldos")
    deposito = models.ForeignKey("companies.Deposito", on_delete=models.CASCADE, related_name="saldos")
    lote = models.ForeignKey(
        "products.Lote", on_delete=models.CASCADE, related_name="saldos", null=True, blank=True
    )
    cantidad = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    costo_promedio_pyg = models.DecimalField(
        max_digits=18, decimal_places=6, default=0,
        help_text="Costo unitario promedio en PYG. Para FIFO/LIFO es informativo "
                   "(valor total de capas vigentes / cantidad); para PROMEDIO es el costo real usado.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Saldo de Stock"
        verbose_name_plural = "Saldos de Stock"
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "deposito", "lote"], nulls_distinct=False,
                name="unique_stock_balance_producto_deposito_lote",
            )
        ]
        indexes = [
            models.Index(fields=["producto", "deposito"]),
        ]

    def __str__(self):
        return f"{self.producto.codigo} @ {self.deposito} = {self.cantidad}"

    @property
    def valor_total_pyg(self):
        return self.cantidad * self.costo_promedio_pyg


class CapaCosto(models.Model):
    """Capa de costo FIFO/LIFO: una porción de stock ingresada a un costo unitario específico."""

    producto = models.ForeignKey("products.Producto", on_delete=models.CASCADE, related_name="capas_costo")
    deposito = models.ForeignKey("companies.Deposito", on_delete=models.CASCADE, related_name="capas_costo")
    lote = models.ForeignKey(
        "products.Lote", on_delete=models.CASCADE, related_name="capas_costo", null=True, blank=True
    )
    cantidad_original = models.DecimalField(max_digits=18, decimal_places=4)
    cantidad_disponible = models.DecimalField(max_digits=18, decimal_places=4)
    costo_unitario_pyg = models.DecimalField(max_digits=18, decimal_places=6)
    fecha_ingreso = models.DateTimeField()
    movimiento_origen = models.ForeignKey(
        "inventory.MovimientoInventario", on_delete=models.PROTECT, related_name="capas_generadas"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Capa de Costo"
        verbose_name_plural = "Capas de Costo"
        ordering = ["fecha_ingreso"]
        indexes = [
            models.Index(fields=["producto", "deposito", "lote", "fecha_ingreso"]),
        ]

    def __str__(self):
        return f"{self.producto.codigo} - {self.cantidad_disponible}/{self.cantidad_original} @ {self.costo_unitario_pyg}"

    @property
    def esta_agotada(self):
        return self.cantidad_disponible <= 0


class StockReserva(models.Model):
    """
    Reserva blanda de stock (Módulo 8 - Pedidos Web: "Reserva de stock").
    No genera movimiento de Kardex ni altera `StockBalance.cantidad`;
    solo resta de la "cantidad disponible para venta"
    (`InventoryService.cantidad_disponible_venta`). Se libera al
    cancelar/rechazar el pedido, o se consume al facturar (momento en
    que sí se genera la salida real vía `InventoryService.registrar_salida`).
    """

    producto = models.ForeignKey("products.Producto", on_delete=models.CASCADE, related_name="reservas")
    deposito = models.ForeignKey("companies.Deposito", on_delete=models.CASCADE, related_name="reservas")
    cantidad = models.DecimalField(max_digits=18, decimal_places=4)
    referencia_tipo = models.CharField(max_length=50, help_text="Ej: PEDIDO_WEB")
    referencia_id = models.CharField(max_length=50)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Reserva de Stock"
        verbose_name_plural = "Reservas de Stock"
        indexes = [
            models.Index(fields=["producto", "deposito", "active"]),
            models.Index(fields=["referencia_tipo", "referencia_id"]),
        ]

    def __str__(self):
        return f"Reserva {self.producto.codigo} x{self.cantidad} ({self.referencia_tipo} #{self.referencia_id})"


class MovimientoInventario(models.Model):
    """Kardex: registro inmutable de todo movimiento de stock."""

    TIPO_ENTRADA = "ENTRADA"
    TIPO_SALIDA = "SALIDA"
    TIPO_AJUSTE_POSITIVO = "AJUSTE_POSITIVO"
    TIPO_AJUSTE_NEGATIVO = "AJUSTE_NEGATIVO"
    TIPO_TRANSFERENCIA_SALIDA = "TRANSFERENCIA_SALIDA"
    TIPO_TRANSFERENCIA_ENTRADA = "TRANSFERENCIA_ENTRADA"
    TIPO_CONTEO_AJUSTE = "CONTEO_AJUSTE"
    TIPO_CHOICES = [
        (TIPO_ENTRADA, "Entrada"),
        (TIPO_SALIDA, "Salida"),
        (TIPO_AJUSTE_POSITIVO, "Ajuste positivo"),
        (TIPO_AJUSTE_NEGATIVO, "Ajuste negativo"),
        (TIPO_TRANSFERENCIA_SALIDA, "Transferencia (salida)"),
        (TIPO_TRANSFERENCIA_ENTRADA, "Transferencia (entrada)"),
        (TIPO_CONTEO_AJUSTE, "Ajuste por conteo físico"),
    ]
    TIPOS_ENTRADA = (TIPO_ENTRADA, TIPO_AJUSTE_POSITIVO, TIPO_TRANSFERENCIA_ENTRADA)
    TIPOS_SALIDA = (TIPO_SALIDA, TIPO_AJUSTE_NEGATIVO, TIPO_TRANSFERENCIA_SALIDA)

    producto = models.ForeignKey("products.Producto", on_delete=models.PROTECT, related_name="movimientos")
    deposito = models.ForeignKey("companies.Deposito", on_delete=models.PROTECT, related_name="movimientos")
    lote = models.ForeignKey(
        "products.Lote", on_delete=models.PROTECT, related_name="movimientos", null=True, blank=True
    )
    ubicacion = models.ForeignKey(
        Ubicacion, on_delete=models.SET_NULL, related_name="movimientos", null=True, blank=True
    )

    tipo_movimiento = models.CharField(max_length=25, choices=TIPO_CHOICES)
    cantidad = models.DecimalField(max_digits=18, decimal_places=4, help_text="Siempre positiva; el signo lo da tipo_movimiento")
    costo_unitario_pyg = models.DecimalField(max_digits=18, decimal_places=6)
    costo_total_pyg = models.DecimalField(max_digits=18, decimal_places=2)

    saldo_cantidad_posterior = models.DecimalField(max_digits=18, decimal_places=4)
    saldo_valor_posterior_pyg = models.DecimalField(max_digits=18, decimal_places=2)

    grupo_transferencia = models.UUIDField(null=True, blank=True, default=None)
    documento_tipo = models.CharField(max_length=50, blank=True)
    documento_referencia = models.CharField(max_length=100, blank=True)
    observaciones = models.TextField(blank=True)

    usuario = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="movimientos_inventario")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimiento de Inventario"
        verbose_name_plural = "Movimientos de Inventario (Kardex)"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["producto", "deposito", "-fecha"]),
            models.Index(fields=["grupo_transferencia"]),
            models.Index(fields=["tipo_movimiento", "-fecha"]),
        ]

    def __str__(self):
        return f"[{self.fecha:%Y-%m-%d %H:%M}] {self.tipo_movimiento} {self.producto.codigo} x{self.cantidad}"

    @property
    def es_entrada(self):
        return self.tipo_movimiento in self.TIPOS_ENTRADA

    def clean(self):
        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError("La cantidad de un movimiento debe ser mayor a cero.")
