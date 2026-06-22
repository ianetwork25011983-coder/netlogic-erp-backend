"""
Módulo 16 - Automatizaciones (motor de reglas).

Decisión de diseño: en vez de un motor 100% genérico que permita
condiciones sobre cualquier campo de cualquier modelo (lo cual exigiría
introspección dinámica de todo el esquema y es un proyecto en sí mismo),
las reglas se evalúan contra un "contexto" ya armado por tipo de
entidad (`PRODUCTO`, `PEDIDO_WEB`). Cada tipo de entidad expone un set
fijo de campos disponibles (ver `RuleEngineService._construir_contexto_*`)
y el usuario combina condiciones sobre esos campos desde la UI — eso
cubre los tres ejemplos del prompt original sin necesitar que el
usuario escriba código ni que el motor permita romper el sistema con
una condición arbitraria mal formada.
"""
from django.core.exceptions import ValidationError
from django.db import models


class ReglaAutomatizacion(models.Model):
    TIPO_ENTIDAD_PRODUCTO = "PRODUCTO"
    TIPO_ENTIDAD_PEDIDO_WEB = "PEDIDO_WEB"
    TIPO_ENTIDAD_CHOICES = [
        (TIPO_ENTIDAD_PRODUCTO, "Producto"),
        (TIPO_ENTIDAD_PEDIDO_WEB, "Pedido Web"),
    ]

    EVALUAR_AL_GUARDAR = "AL_GUARDAR"
    EVALUAR_PERIODICO = "PERIODICO"
    EVALUAR_EN_CHOICES = [
        (EVALUAR_AL_GUARDAR, "Al crear/actualizar el registro"),
        (EVALUAR_PERIODICO, "Periódicamente (Celery Beat)"),
    ]

    ACCION_GENERAR_SOLICITUD_COMPRA = "GENERAR_SOLICITUD_COMPRA"
    ACCION_GENERAR_ALERTA = "GENERAR_ALERTA"
    ACCION_ASIGNAR_PRIORIDAD = "ASIGNAR_PRIORIDAD"
    ACCION_CHOICES = [
        (ACCION_GENERAR_SOLICITUD_COMPRA, "Generar solicitud de compra"),
        (ACCION_GENERAR_ALERTA, "Generar alerta"),
        (ACCION_ASIGNAR_PRIORIDAD, "Asignar prioridad"),
    ]

    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="reglas_automatizacion")
    nombre = models.CharField(max_length=150)
    descripcion = models.CharField(max_length=255, blank=True)
    tipo_entidad = models.CharField(max_length=15, choices=TIPO_ENTIDAD_CHOICES)
    evaluar_en = models.CharField(max_length=12, choices=EVALUAR_EN_CHOICES, default=EVALUAR_AL_GUARDAR)
    frecuencia_horas = models.PositiveSmallIntegerField(
        default=24, help_text="Solo aplica si evaluar_en=PERIODICO"
    )

    condiciones = models.JSONField(
        help_text=(
            'Lista de condiciones (todas deben cumplirse - AND). Cada una: '
            '{"campo": "stock_actual", "operador": "<", "campo_comparacion": "stock_minimo"} '
            'o {"campo": "dias_sin_movimiento", "operador": ">", "valor": 180}'
        )
    )
    accion = models.CharField(max_length=30, choices=ACCION_CHOICES)
    parametros_accion = models.JSONField(
        default=dict, blank=True,
        help_text='Ej: {"prioridad": "ALTA"} para ASIGNAR_PRIORIDAD, {"mensaje": "..."} para GENERAR_ALERTA',
    )

    active = models.BooleanField(default=True)
    ultima_ejecucion = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Regla de Automatización"
        verbose_name_plural = "Reglas de Automatización"
        ordering = ["empresa", "nombre"]

    def __str__(self):
        return self.nombre

    def clean(self):
        if not isinstance(self.condiciones, list) or not self.condiciones:
            raise ValidationError("'condiciones' debe ser una lista no vacía de condiciones.")
        for cond in self.condiciones:
            if "campo" not in cond or "operador" not in cond:
                raise ValidationError("Cada condición necesita al menos 'campo' y 'operador'.")
            if "valor" not in cond and "campo_comparacion" not in cond:
                raise ValidationError("Cada condición necesita 'valor' o 'campo_comparacion'.")


class Alerta(models.Model):
    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="alertas")
    regla = models.ForeignKey(
        ReglaAutomatizacion, on_delete=models.SET_NULL, related_name="alertas_generadas", null=True, blank=True
    )
    objeto_tipo = models.CharField(max_length=50, blank=True)
    objeto_id = models.CharField(max_length=50, blank=True)
    mensaje = models.TextField()
    leida = models.BooleanField(default=False)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Alerta"
        verbose_name_plural = "Alertas"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["empresa", "leida", "-fecha"]),
        ]

    def __str__(self):
        return self.mensaje[:80]


class EjecucionRegla(models.Model):
    """Bitácora de cada vez que se evalúa una regla, cumpla o no la condición — para auditoría y depuración."""

    regla = models.ForeignKey(ReglaAutomatizacion, on_delete=models.CASCADE, related_name="ejecuciones")
    objeto_tipo = models.CharField(max_length=50, blank=True)
    objeto_id = models.CharField(max_length=50, blank=True)
    condicion_cumplida = models.BooleanField()
    accion_ejecutada = models.BooleanField(default=False)
    contexto_evaluado = models.JSONField(default=dict, blank=True)
    resultado = models.CharField(max_length=255, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ejecución de Regla"
        verbose_name_plural = "Ejecuciones de Regla"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.regla.nombre} - {'cumplida' if self.condicion_cumplida else 'no cumplida'}"
