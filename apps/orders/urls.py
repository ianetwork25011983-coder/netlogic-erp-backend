from rest_framework.routers import DefaultRouter

from django.urls import path

from . import views

router = DefaultRouter()
router.register("pedidos", views.PedidoWebViewSet, basename="pedidoweb")

urlpatterns = [
    path("pedidos/crear/", views.CrearPedidoWebView.as_view(), name="crear-pedido-web"),
    path("pedidos/<int:pedido_id>/aprobar/", views.AprobarPedidoView.as_view(), name="aprobar-pedido-web"),
    path("pedidos/<int:pedido_id>/rechazar/", views.RechazarPedidoView.as_view(), name="rechazar-pedido-web"),
    path("pedidos/<int:pedido_id>/cancelar/", views.CancelarPedidoView.as_view(), name="cancelar-pedido-web"),
    path("pedidos/<int:pedido_id>/en-picking/", views.MarcarEnPickingView.as_view(), name="picking-pedido-web"),
    path("pedidos/<int:pedido_id>/facturar/", views.FacturarPedidoView.as_view(), name="facturar-pedido-web"),
    path("pedidos/<int:pedido_id>/despachar/", views.MarcarDespachadoView.as_view(), name="despachar-pedido-web"),
    path("pedidos/<int:pedido_id>/entregar/", views.MarcarEntregadoView.as_view(), name="entregar-pedido-web"),
] + router.urls
