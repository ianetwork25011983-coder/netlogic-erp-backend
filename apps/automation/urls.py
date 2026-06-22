from rest_framework.routers import DefaultRouter

from django.urls import path

from . import views

router = DefaultRouter()
router.register("reglas", views.ReglaAutomatizacionViewSet, basename="reglaautomatizacion")
router.register("alertas", views.AlertaViewSet, basename="alerta")
router.register("ejecuciones", views.EjecucionReglaViewSet, basename="ejecucionregla")

urlpatterns = [
    path("alertas/<int:alerta_id>/marcar-leida/", views.MarcarAlertaLeidaView.as_view(), name="marcar-alerta-leida"),
    path("evaluar/producto/", views.EvaluarProductoView.as_view(), name="evaluar-reglas-producto"),
    path("evaluar/pedido-web/", views.EvaluarPedidoWebView.as_view(), name="evaluar-reglas-pedido-web"),
] + router.urls
