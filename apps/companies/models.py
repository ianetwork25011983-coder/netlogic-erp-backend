"""
Módulo 2 - Empresas y Sucursales.

Soporta multiempresa real (cada Empresa tiene su propia configuración
fiscal e incluso su propia moneda operativa por defecto), con sucursales,
depósitos ilimitados, centros de distribución y puntos de venta.
"""
from django.core.exceptions import ValidationError
from django.db import models


class Empresa(models.Model):
    TIPO_CONTRIBUYENTE_CHOICES = [
        ("FISICA", "Persona Física"),
        ("JURIDICA", "Persona Jurídica"),
    ]

    razon_social = models.CharField(max_length=200)
    nombre_comercial = models.CharField(max_length=200, blank=True)
    ruc = models.CharField(
        "RUC / Identificación fiscal", max_length=20, unique=True
    )
    tipo_contribuyente = models.CharField(
        max_length=10, choices=TIPO_CONTRIBUYENTE_CHOICES, default="JURIDICA"
    )

    # Configuración fiscal (facturación electrónica - Paraguay/SET)
    timbrado_numero = models.CharField(max_length=20, blank=True)
    timbrado_vencimiento = models.DateField(null=True, blank=True)

    moneda_default = models.ForeignKey(
        "currencies.Currency",
        on_delete=models.PROTECT,
        related_name="empresas",
        help_text="Moneda en la que esta empresa emite presupuestos/facturas por defecto",
    )

    direccion = models.CharField(max_length=255, blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to="empresas/logos/", null=True, blank=True)

    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ["razon_social"]

    def __str__(self):
        return self.nombre_comercial or self.razon_social


class Sucursal(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="sucursales")
    codigo = models.CharField(max_length=10)
    nombre = models.CharField(max_length=150)
    direccion = models.CharField(max_length=255, blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    es_casa_matriz = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sucursal"
        verbose_name_plural = "Sucursales"
        ordering = ["empresa", "codigo"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "codigo"], name="unique_sucursal_codigo_por_empresa"
            )
        ]

    def __str__(self):
        return f"{self.empresa} - {self.nombre}"

    def clean(self):
        if self.es_casa_matriz:
            qs = Sucursal.objects.filter(empresa=self.empresa, es_casa_matriz=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    "Esta empresa ya tiene una sucursal marcada como casa matriz."
                )


class Deposito(models.Model):
    """
    Depósito físico de almacenamiento. No hay límite de depósitos por
    sucursal ("depósitos ilimitados"). El campo `tipo` permite distinguir
    un depósito normal de un centro de distribución sin duplicar modelos.
    """

    TIPO_ALMACEN = "ALMACEN"
    TIPO_TRANSITO = "TRANSITO"
    TIPO_DEVOLUCION = "DEVOLUCION"
    TIPO_CENTRO_DISTRIBUCION = "CENTRO_DISTRIBUCION"
    TIPO_CHOICES = [
        (TIPO_ALMACEN, "Almacén"),
        (TIPO_TRANSITO, "Tránsito"),
        (TIPO_DEVOLUCION, "Devoluciones"),
        (TIPO_CENTRO_DISTRIBUCION, "Centro de Distribución"),
    ]

    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, related_name="depositos")
    codigo = models.CharField(max_length=10)
    nombre = models.CharField(max_length=150)
    tipo = models.CharField(max_length=25, choices=TIPO_CHOICES, default=TIPO_ALMACEN)
    ubicacion_fisica = models.CharField(
        max_length=255, blank=True, help_text="Dirección física si difiere de la sucursal"
    )
    permite_venta_directa = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Depósito"
        verbose_name_plural = "Depósitos"
        ordering = ["sucursal", "codigo"]
        constraints = [
            models.UniqueConstraint(
                fields=["sucursal", "codigo"], name="unique_deposito_codigo_por_sucursal"
            )
        ]

    def __str__(self):
        return f"{self.sucursal} - {self.nombre}"


class PuntoVenta(models.Model):
    """
    Punto de venta / caja, ligado a la numeración de timbrado para
    facturación electrónica (establecimiento + punto de expedición).
    """

    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, related_name="puntos_venta")
    codigo = models.CharField(max_length=10)
    nombre = models.CharField(max_length=150)
    establecimiento = models.CharField(max_length=3, help_text="Código de establecimiento SET")
    punto_expedicion = models.CharField(max_length=3, help_text="Código de punto de expedición SET")
    deposito_predeterminado = models.ForeignKey(
        Deposito, on_delete=models.PROTECT, related_name="puntos_venta", null=True, blank=True
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Punto de Venta"
        verbose_name_plural = "Puntos de Venta"
        ordering = ["sucursal", "codigo"]
        constraints = [
            models.UniqueConstraint(
                fields=["sucursal", "codigo"], name="unique_pv_codigo_por_sucursal"
            )
        ]

    def __str__(self):
        return f"{self.sucursal} - PV {self.codigo}"
