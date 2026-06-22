"""
Tarea periódica del motor de reglas (Módulo 16).

Para activarla en producción, programar en Celery Beat (vía el admin de
`django_celery_beat`, ya instalado desde la Fase 0) una tarea periódica
que llame a `evaluar_reglas_periodicas_todas_las_empresas`, con la
frecuencia que se prefiera (ej. cada hora). No se ejecuta solo por
existir esta función: hace falta un worker de Celery corriendo y la
tarea periódica creada en `/admin/django_celery_beat/periodictask/`.
"""
from celery import shared_task


@shared_task
def evaluar_reglas_periodicas_todas_las_empresas():
    from apps.companies.models import Empresa

    from .services import RuleEngineService

    total_resultados = 0
    for empresa in Empresa.objects.filter(active=True):
        resultados = RuleEngineService.evaluar_periodicas_de_empresa(empresa)
        total_resultados += len(resultados)
    return f"Reglas periódicas evaluadas: {total_resultados} evaluaciones en total."
