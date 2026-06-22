"""
Proveedores - versión mínima para Fase 1.

Solo lo necesario para que Producto pueda referenciar un "proveedor
principal". El Módulo 9 (Compras) de una fase posterior va a extender
esto con cotizaciones, comparación de costos/plazos e historial de
compras por proveedor.
"""
from django.db import models


class Proveedor(models.Model):
    empresa = models.ForeignKey(
        "companies.Empresa", on_delete=models.CASCADE, related_name="proveedores"
    )
    razon_social = models.CharField(max_length=200)
    nombre_comercial = models.CharField(max_length=200, blank=True)
    ruc = models.CharField(max_length=20)
    contacto_nombre = models.CharField(max_length=150, blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    moneda_default = models.ForeignKey(
        "currencies.Currency", on_delete=models.PROTECT, related_name="proveedores"
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ["razon_social"]
        constraints = [
            models.UniqueConstraint(fields=["empresa", "ruc"], name="unique_proveedor_ruc_por_empresa")
        ]

    def __str__(self):
        return self.nombre_comercial or self.razon_social
