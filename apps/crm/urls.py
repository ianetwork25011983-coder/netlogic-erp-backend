from rest_framework.routers import DefaultRouter

from django.urls import path

from . import views

router = DefaultRouter()
router.register("prospectos", views.ProspectoViewSet, basename="prospecto")
router.register("contactos", views.ContactoViewSet, basename="contacto")
router.register("etapas-pipeline", views.EtapaPipelineViewSet, basename="etapapipeline")
router.register("oportunidades", views.OportunidadViewSet, basename="oportunidad")
router.register("interacciones", views.InteraccionViewSet, basename="interaccion")

urlpatterns = [
    path("prospectos/<int:prospecto_id>/convertir/", views.ConvertirProspectoView.as_view(), name="convertir-prospecto"),
    path(
        "oportunidades/<int:oportunidad_id>/mover-etapa/",
        views.MoverEtapaOportunidadView.as_view(),
        name="mover-etapa-oportunidad",
    ),
    path("pipeline/resumen/", views.PipelineResumenView.as_view(), name="pipeline-resumen"),
] + router.urls
