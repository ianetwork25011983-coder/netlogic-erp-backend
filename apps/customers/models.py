"""
Clientes - versión mínima para Fase 2.

Solo lo necesario para que Facturación pueda emitir documentos a un
cliente. El Módulo 6 (CRM) de una fase posterior va a extender esto con
prospectos, contactos, historial comercial, seguimiento y pipeline de
ventas.
"""
from django.db import models


class Cliente(models.Model):
    TIPO_CONTRIBUYENTE_CHOICES = [
        ("FISICA", "Persona Física"),
        ("JURIDICA", "Persona Jurídica"),
        ("EXTRANJERO", "Cliente del Exterior"),
    ]

    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="clientes")
    razon_social = models.CharField(max_length=200)
    nombre_comercial = models.CharField(max_length=200, blank=True)
    ruc = models.CharField(max_length=20, help_text="RUC, CI o documento del exterior")
    tipo_contribuyente = models.CharField(max_length=12, choices=TIPO_CONTRIBUYENTE_CHOICES, default="FISICA")

    contacto_nombre = models.CharField(max_length=150, blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.CharField(max_length=255, blank=True)

    moneda_default = models.ForeignKey(
        "currencies.Currency", on_delete=models.PROTECT, related_name="clientes"
    )
    limite_credito = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    dias_credito = models.PositiveSmallIntegerField(default=0)
    es_vip = models.BooleanField(
        default=False, help_text="Usado por el Módulo 16 (motor de reglas) para priorizar sus pedidos automáticamente"
    )

    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["razon_social"]
        constraints = [
            models.UniqueConstraint(fields=["empresa", "ruc"], name="unique_cliente_ruc_por_empresa")
        ]

    def __str__(self):
        return self.nombre_comercial or self.razon_social
