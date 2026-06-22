"""
Módulo 19 - IA Copiloto del ERP.

`ConsultaCopiloto` deja registro de qué se preguntó y qué intención se
detectó — útil tanto para auditoría como para ver, con el tiempo, qué
preguntas hace la gente realmente y si el catálogo de intenciones
reconocidas necesita ampliarse.
"""
from django.db import models


class ConsultaCopiloto(models.Model):
    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="consultas_copiloto")
    usuario = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, related_name="consultas_copiloto", null=True)
    pregunta = models.TextField()
    intent_detectado = models.CharField(max_length=50, blank=True)
    respuesta_resumen = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Consulta al Copiloto"
        verbose_name_plural = "Consultas al Copiloto"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.fecha:%Y-%m-%d %H:%M} - {self.intent_detectado or 'sin_intent'}"
