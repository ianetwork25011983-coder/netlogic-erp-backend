"""
Núcleo de monedas multi-divisa.

Decisión de diseño (confirmada con el cliente):
- PYG es la moneda base del sistema. Todo el inventario, costos y reportes
  se valorizan internamente en PYG, sin importar en qué moneda se haya
  facturado o comprado.
- Monedas operativas: USD, BRL (real), ARS (peso argentino), además de PYG.
- Las tasas de cambio se cargan manualmente de forma periódica (no hay
  integración a una API de cotización en tiempo real). Cada tasa queda
  fechada y queda como registro histórico inmutable.
- Toda transacción (factura, compra, movimiento de stock) debe persistir
  tanto el monto en su moneda original como el monto convertido a PYG con
  la tasa vigente en el momento de la operación. Esto evita que un cambio
  de cotización futuro distorsione retroactivamente el Kardex valorizado,
  el dashboard financiero o los reportes ya cerrados.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models


class Currency(models.Model):
    """Catálogo de monedas soportadas por el sistema."""

    code = models.CharField(
        max_length=3,
        unique=True,
        help_text="Código ISO 4217 (PYG, USD, BRL, ARS)",
    )
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=5, help_text="Ej: ₲, $, R$")
    decimal_places = models.PositiveSmallIntegerField(
        default=2,
        help_text="0 para PYG (no usa decimales), 2 para USD/BRL/ARS",
    )
    is_base = models.BooleanField(
        default=False,
        help_text="Marca la moneda base del sistema. Solo puede haber una.",
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Moneda"
        verbose_name_plural = "Monedas"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        if self.is_base:
            qs = Currency.objects.filter(is_base=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    "Ya existe una moneda base configurada. "
                    "Debe desmarcar la anterior antes de asignar una nueva."
                )

    def save(self, *args, **kwargs):
        self.full_clean(exclude=[f.name for f in self._meta.fields if f.name not in ("is_base",)])
        super().save(*args, **kwargs)

    @classmethod
    def get_base(cls):
        return cls.objects.get(is_base=True)


class ExchangeRate(models.Model):
    """
    Tasa de cambio de una moneda hacia la moneda base (PYG), vigente desde
    una fecha determinada. Registro histórico e inmutable: no se edita una
    tasa ya cargada, se carga una nueva con fecha más reciente.
    """

    SOURCE_MANUAL = "MANUAL"
    SOURCE_IMPORTED = "IMPORTADO"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Carga manual"),
        (SOURCE_IMPORTED, "Importado (Excel/CSV)"),
    ]

    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="exchange_rates",
    )
    rate_to_base = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        help_text="Cuántas unidades de la moneda base (PYG) equivale 1 unidad de esta moneda",
    )
    effective_date = models.DateField(
        help_text="Fecha desde la cual esta tasa está vigente",
    )
    source = models.CharField(max_length=12, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    loaded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="exchange_rates_loaded",
        null=True,
        blank=True,
    )
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tasa de cambio"
        verbose_name_plural = "Tasas de cambio"
        ordering = ["-effective_date", "currency"]
        constraints = [
            models.UniqueConstraint(
                fields=["currency", "effective_date"],
                name="unique_currency_rate_per_day",
            )
        ]
        indexes = [
            models.Index(fields=["currency", "-effective_date"]),
        ]

    def __str__(self):
        return f"{self.currency.code} -> {self.rate_to_base} PYG ({self.effective_date})"

    def clean(self):
        if self.currency_id and self.currency.is_base:
            raise ValidationError(
                "No se puede cargar una tasa de cambio para la moneda base."
            )
        if self.rate_to_base is not None and self.rate_to_base <= 0:
            raise ValidationError("La tasa de cambio debe ser mayor a cero.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
