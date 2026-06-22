"""
Módulo 10 - Facturación.

Decisión de diseño: un solo modelo `DocumentoVenta` cubre Factura, Nota
de Crédito, Nota de Débito, Presupuesto y Remisión (campo
`tipo_documento`), porque comparten ~90% de su estructura (cabecera +
items + totales). `documento_referencia` enlaza una NC/ND a la factura
que afecta, o una Remisión a la factura que la origina.

Los precios de línea son NETOS (sin impuesto incluido); el impuesto se
calcula aparte por línea según `Producto.impuesto` (o el impuesto
indicado manualmente en el item) y se suma al total. Esto permite
desglosar IVA 10%/5%/exento por separado, como exige la facturación
electrónica paraguaya.

Ningún documento descuenta/repone stock directamente: eso lo hace
`BillingService`, que es el único punto de entrada que llama a
`InventoryService`, igual que Compras.
"""
from django.core.exceptions import ValidationError
from django.db import models


class SecuenciaDocumento(models.Model):
    """Contador correlativo por punto de venta + tipo de documento, para numeración fiscal."""

    punto_venta = models.ForeignKey(
        "companies.PuntoVenta", on_delete=models.CASCADE, related_name="secuencias_documento"
    )
    tipo_documento = models.CharField(max_length=15)
    ultimo_numero = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Secuencia de Documento"
        verbose_name_plural = "Secuencias de Documento"
        constraints = [
            models.UniqueConstraint(
                fields=["punto_venta", "tipo_documento"], name="unique_secuencia_por_pv_y_tipo"
            )
        ]

    def __str__(self):
        return f"{self.punto_venta} - {self.tipo_documento}: {self.ultimo_numero}"


class DocumentoVenta(models.Model):
    TIPO_FACTURA = "FACTURA"
    TIPO_NOTA_CREDITO = "NOTA_CREDITO"
    TIPO_NOTA_DEBITO = "NOTA_DEBITO"
    TIPO_PRESUPUESTO = "PRESUPUESTO"
    TIPO_REMISION = "REMISION"
    TIPO_CHOICES = [
        (TIPO_FACTURA, "Factura"),
        (TIPO_NOTA_CREDITO, "Nota de Crédito"),
        (TIPO_NOTA_DEBITO, "Nota de Débito"),
        (TIPO_PRESUPUESTO, "Presupuesto"),
        (TIPO_REMISION, "Remisión"),
    ]

    CONDICION_CONTADO = "CONTADO"
    CONDICION_CREDITO = "CREDITO"
    CONDICION_CHOICES = [
        (CONDICION_CONTADO, "Contado"),
        (CONDICION_CREDITO, "Crédito"),
    ]

    ESTADO_BORRADOR = "BORRADOR"
    ESTADO_EMITIDA = "EMITIDA"
    ESTADO_ANULADA = "ANULADA"
    ESTADO_CHOICES = [
        (ESTADO_BORRADOR, "Borrador"),
        (ESTADO_EMITIDA, "Emitida"),
        (ESTADO_ANULADA, "Anulada"),
    ]

    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="documentos_venta")
    sucursal = models.ForeignKey("companies.Sucursal", on_delete=models.CASCADE, related_name="documentos_venta")
    punto_venta = models.ForeignKey(
        "companies.PuntoVenta", on_delete=models.PROTECT, related_name="documentos_venta"
    )
    tipo_documento = models.CharField(max_length=15, choices=TIPO_CHOICES)
    numero = models.CharField(max_length=20, help_text="Formato establecimiento-puntoExp-secuencial")

    cliente = models.ForeignKey("customers.Cliente", on_delete=models.PROTECT, related_name="documentos_venta")
    documento_referencia = models.ForeignKey(
        "self", on_delete=models.SET_NULL, related_name="documentos_relacionados", null=True, blank=True,
        help_text="Factura que afecta esta NC/ND, o factura/presupuesto de origen de esta Remisión",
    )

    moneda = models.ForeignKey("currencies.Currency", on_delete=models.PROTECT, related_name="documentos_venta")
    tipo_cambio_pyg = models.DecimalField(
        max_digits=18, decimal_places=6, default=1,
        help_text="Tasa de cambio a PYG vigente al momento de la emisión (snapshot inmutable)",
    )
    condicion_venta = models.CharField(max_length=10, choices=CONDICION_CHOICES, default=CONDICION_CONTADO)
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default=ESTADO_BORRADOR)

    afecta_inventario = models.BooleanField(
        default=False,
        help_text="Si está marcado, al emitir el documento se descuenta (o repone, en NC) stock real",
    )
    deposito_salida = models.ForeignKey(
        "companies.Deposito", on_delete=models.PROTECT, related_name="documentos_venta",
        null=True, blank=True, help_text="Obligatorio si afecta_inventario=True",
    )

    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    impuesto_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    descuento_global = models.DecimalField(
        max_digits=18, decimal_places=2, default=0,
        help_text="Descuento adicional a nivel de documento (ej. cupón), aplicado después de impuestos. "
                   "No se redistribuye proporcionalmente entre líneas ni recalcula el IVA por línea.",
    )
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_pyg = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    saldo_pendiente = models.DecimalField(
        max_digits=18, decimal_places=2, default=0,
        help_text="Solo relevante para FACTURA con condición CREDITO; Tesorería (fase posterior) lo actualiza con los cobros",
    )

    fecha_emision = models.DateField()
    fecha_vencimiento = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True)
    usuario = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="documentos_venta")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Documento de Venta"
        verbose_name_plural = "Documentos de Venta"
        ordering = ["-fecha_emision", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["punto_venta", "tipo_documento", "numero"], name="unique_numero_por_pv_y_tipo"
            )
        ]
        indexes = [
            models.Index(fields=["empresa", "tipo_documento", "-fecha_emision"]),
            models.Index(fields=["cliente", "-fecha_emision"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_documento_display()} {self.numero} - {self.cliente}"

    def clean(self):
        if self.afecta_inventario and not self.deposito_salida_id:
            raise ValidationError("Si el documento afecta inventario, debe indicar el depósito de salida.")
        if self.tipo_documento in (self.TIPO_NOTA_CREDITO, self.TIPO_NOTA_DEBITO) and not self.documento_referencia_id:
            raise ValidationError("Una Nota de Crédito/Débito debe referenciar la factura que afecta.")

    def desglose_impuestos(self):
        """Agrupa el impuesto por tasa, para el formato de factura electrónica (IVA 10%/5%/exento)."""
        desglose = {}
        for item in self.items.select_related("impuesto").all():
            tasa_key = str(item.tasa_impuesto_aplicada)
            grupo = desglose.setdefault(tasa_key, {"tasa": item.tasa_impuesto_aplicada, "base": 0, "impuesto": 0})
            grupo["base"] += item.subtotal_linea
            grupo["impuesto"] += item.impuesto_linea
        return desglose


class DocumentoVentaItem(models.Model):
    documento = models.ForeignKey(DocumentoVenta, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey("products.Producto", on_delete=models.PROTECT, related_name="+")
    descripcion = models.CharField(max_length=255, help_text="Snapshot del nombre del producto al momento de la venta")

    cantidad = models.DecimalField(max_digits=18, decimal_places=4)
    precio_unitario = models.DecimalField(max_digits=18, decimal_places=6, help_text="Precio neto, sin impuesto")
    descuento_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    impuesto = models.ForeignKey(
        "products.Impuesto", on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )
    tasa_impuesto_aplicada = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, help_text="Snapshot de la tasa al momento de la venta"
    )

    subtotal_linea = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    impuesto_linea = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_linea = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    movimiento_inventario = models.ForeignKey(
        "inventory.MovimientoInventario", on_delete=models.PROTECT, related_name="+", null=True, blank=True,
        help_text="Movimiento de stock generado por esta línea, si el documento afecta inventario",
    )

    class Meta:
        verbose_name = "Ítem de Documento de Venta"
        verbose_name_plural = "Ítems de Documento de Venta"

    def __str__(self):
        return f"{self.documento.numero} - {self.descripcion} x{self.cantidad}"
