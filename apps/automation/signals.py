"""
Conecta la creación de un PedidoWeb a la evaluación automática de
reglas tipo PEDIDO_WEB con evaluar_en=AL_GUARDAR (ej. "cliente VIP hace
un pedido -> asignar prioridad").
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.orders.models import PedidoWeb

from .services import RuleEngineService


@receiver(post_save, sender=PedidoWeb)
def evaluar_reglas_pedido_web(sender, instance, created, **kwargs):
    if not created:
        return
    RuleEngineService.evaluar_pedido_web(instance)
