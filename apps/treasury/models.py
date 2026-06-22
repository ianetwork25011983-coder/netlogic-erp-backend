"""
Módulo 11 - Caja y Tesorería.

`AperturaCaja` representa una sesión de caja (desde que se abre hasta
que se cierra). Todos los ingresos/egresos de esa sesión se cuelgan de
`MovimientoCaja`. `CierreCaja` es el arqueo: compara lo contado
físicamente contra lo esperado según los movimientos en efectivo,
dejando la diferencia registrada (nunca se "ajusta" el conteo, solo se
documenta).

Los cobros de facturas y pagos a proveedores pasan por
`TreasuryService.registrar_cobro_factura()` /
`registrar_pago_proveedor()`, que son los únicos puntos que actualizan
`DocumentoVenta.saldo_pendiente` / `FacturaProveedor.saldo_pendiente`.
"""
from django.core.exceptions import ValidationError
from django.db import models


class Caja(models.Model):
    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="cajas")
    sucursal = models.ForeignKey("companies.Sucursal", on_delete=models.CASCADE, related_name="cajas")
    punto_venta = models.ForeignKey(
        "companies.PuntoVenta", on_delete=models.SET_NULL, related_name="cajas", null=True, blank=True
    )
    codigo = models.CharField(max_length=10)
    nombre = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Caja"
        verbose_name_plural = "Cajas"
        ordering = ["sucursal", "codigo"]
        constraints = [
            models.UniqueConstraint(fields=["sucursal", "codigo"], name="unique_caja_codigo_por_sucursal")
        ]

    def __str__(self):
        return f"{self.sucursal} - {self.nombre}"


class AperturaCaja(models.Model):
    ESTADO_ABIERTA = "ABIERTA"
    ESTADO_CERRADA = "CERRADA"
    ESTADO_CHOICES = [
        (ESTADO_ABIERTA, "Abierta"),
        (ESTADO_CERRADA, "Cerrada"),
    ]

    caja = models.ForeignKey(Caja, on_delete=models.PROTECT, related_name="aperturas")
    usuario = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="aperturas_caja")
    monto_inicial = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    moneda = models.ForeignKey("currencies.Currency", on_delete=models.PROTECT, related_name="aperturas_caja")
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default=ESTADO_ABIERTA)
    observaciones = models.TextField(blank=True)
    fecha_apertura = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Apertura de Caja"
        verbose_name_plural = "Aperturas de Caja"
        ordering = ["-fecha_apertura"]
        constraints = [
            models.UniqueConstraint(
                fields=["caja"], condition=models.Q(estado="ABIERTA"), name="unique_apertura_activa_por_caja"
            )
        ]

    def __str__(self):
        return f"Apertura {self.caja} - {self.fecha_apertura:%Y-%m-%d %H:%M}"


class MovimientoCaja(models.Model):
    TIPO_INGRESO = "INGRESO"
    TIPO_EGRESO = "EGRESO"
    TIPO_CHOICES = [(TIPO_INGRESO, "Ingreso"), (TIPO_EGRESO, "Egreso")]

    CONCEPTO_COBRO_FACTURA = "COBRO_FACTURA"
    CONCEPTO_PAGO_PROVEEDOR = "PAGO_PROVEEDOR"
    CONCEPTO_GASTO = "GASTO"
    CONCEPTO_RETIRO = "RETIRO"
    CONCEPTO_DEPOSITO_BANCO = "DEPOSITO_BANCO"
    CONCEPTO_OTRO = "OTRO"
    CONCEPTO_CHOICES = [
        (CONCEPTO_COBRO_FACTURA, "Cobro de factura"),
        (CONCEPTO_PAGO_PROVEEDOR, "Pago a proveedor"),
        (CONCEPTO_GASTO, "Gasto"),
        (CONCEPTO_RETIRO, "Retiro"),
        (CONCEPTO_DEPOSITO_BANCO, "Depósito a banco"),
        (CONCEPTO_OTRO, "Otro"),
    ]

    MEDIO_EFECTIVO = "EFECTIVO"
    MEDIO_TRANSFERENCIA = "TRANSFERENCIA"
    MEDIO_TARJETA_DEBITO = "TARJETA_DEBITO"
    MEDIO_TARJETA_CREDITO = "TARJETA_CREDITO"
    MEDIO_QR = "QR"
    MEDIO_CHEQUE = "CHEQUE"
    MEDIO_CHOICES = [
        (MEDIO_EFECTIVO, "Efectivo"),
        (MEDIO_TRANSFERENCIA, "Transferencia"),
        (MEDIO_TARJETA_DEBITO, "Tarjeta de Débito"),
        (MEDIO_TARJETA_CREDITO, "Tarjeta de Crédito"),
        (MEDIO_QR, "QR"),
        (MEDIO_CHEQUE, "Cheque"),
    ]

    apertura_caja = models.ForeignKey(AperturaCaja, on_delete=models.PROTECT, related_name="movimientos")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    concepto = models.CharField(max_length=20, choices=CONCEPTO_CHOICES)
    medio_pago = models.CharField(max_length=15, choices=MEDIO_CHOICES, default=MEDIO_EFECTIVO)
    monto = models.DecimalField(max_digits=18, decimal_places=2)
    moneda = models.ForeignKey("currencies.Currency", on_delete=models.PROTECT, related_name="movimientos_caja")

    referencia_tipo = models.CharField(max_length=50, blank=True, help_text="Ej: DOCUMENTO_VENTA, FACTURA_PROVEEDOR")
    referencia_id = models.CharField(max_length=50, blank=True)

    usuario = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="movimientos_caja")
    observaciones = models.CharField(max_length=255, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimiento de Caja"
        verbose_name_plural = "Movimientos de Caja"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["apertura_caja", "tipo"]),
            models.Index(fields=["referencia_tipo", "referencia_id"]),
        ]

    def __str__(self):
        return f"{self.tipo} {self.monto} {self.moneda.code} - {self.concepto}"

    def clean(self):
        if self.monto is not None and self.monto <= 0:
            raise ValidationError("El monto debe ser mayor a cero.")


class CierreCaja(models.Model):
    apertura_caja = models.OneToOneField(AperturaCaja, on_delete=models.PROTECT, related_name="cierre")
    monto_contado_efectivo = models.DecimalField(max_digits=18, decimal_places=2)
    monto_esperado_efectivo = models.DecimalField(max_digits=18, decimal_places=2)
    diferencia = models.DecimalField(max_digits=18, decimal_places=2)
    usuario = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="cierres_caja")
    observaciones = models.TextField(blank=True)
    fecha_cierre = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cierre de Caja (Arqueo)"
        verbose_name_plural = "Cierres de Caja (Arqueos)"
        ordering = ["-fecha_cierre"]

    def __str__(self):
        return f"Cierre {self.apertura_caja.caja} - {self.fecha_cierre:%Y-%m-%d}"


class Banco(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Banco"
        verbose_name_plural = "Bancos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class CuentaBancaria(models.Model):
    TIPO_CORRIENTE = "CORRIENTE"
    TIPO_AHORRO = "AHORRO"
    TIPO_CHOICES = [(TIPO_CORRIENTE, "Cuenta Corriente"), (TIPO_AHORRO, "Caja de Ahorro")]

    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="cuentas_bancarias")
    banco = models.ForeignKey(Banco, on_delete=models.PROTECT, related_name="cuentas")
    numero_cuenta = models.CharField(max_length=50)
    tipo_cuenta = models.CharField(max_length=10, choices=TIPO_CHOICES, default=TIPO_CORRIENTE)
    moneda = models.ForeignKey("currencies.Currency", on_delete=models.PROTECT, related_name="cuentas_bancarias")
    saldo_actual = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Cuenta Bancaria"
        verbose_name_plural = "Cuentas Bancarias"
        constraints = [
            models.UniqueConstraint(fields=["banco", "numero_cuenta"], name="unique_cuenta_por_banco")
        ]

    def __str__(self):
        return f"{self.banco} - {self.numero_cuenta}"


class MovimientoBancario(models.Model):
    TIPO_DEPOSITO = "DEPOSITO"
    TIPO_RETIRO = "RETIRO"
    TIPO_TRANSFERENCIA_ENTRADA = "TRANSFERENCIA_ENTRADA"
    TIPO_TRANSFERENCIA_SALIDA = "TRANSFERENCIA_SALIDA"
    TIPO_CHOICES = [
        (TIPO_DEPOSITO, "Depósito"),
        (TIPO_RETIRO, "Retiro"),
        (TIPO_TRANSFERENCIA_ENTRADA, "Transferencia recibida"),
        (TIPO_TRANSFERENCIA_SALIDA, "Transferencia enviada"),
    ]

    cuenta_bancaria = models.ForeignKey(CuentaBancaria, on_delete=models.PROTECT, related_name="movimientos")
    tipo = models.CharField(max_length=25, choices=TIPO_CHOICES)
    monto = models.DecimalField(max_digits=18, decimal_places=2)
    saldo_posterior = models.DecimalField(max_digits=18, decimal_places=2)
    referencia = models.CharField(max_length=100, blank=True)
    observaciones = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="movimientos_bancarios")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimiento Bancario"
        verbose_name_plural = "Movimientos Bancarios"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.tipo} {self.monto} - {self.cuenta_bancaria}"

    def clean(self):
        if self.monto is not None and self.monto <= 0:
            raise ValidationError("El monto debe ser mayor a cero.")
