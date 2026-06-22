from django.urls import path

from . import views

urlpatterns = [
    path("auth/login/", views.PortalLoginView.as_view(), name="portal-login"),
    path("auth/me/", views.PortalMeView.as_view(), name="portal-me"),
    path("auth/cambiar-password/", views.PortalChangePasswordView.as_view(), name="portal-cambiar-password"),
    path("admin/provisionar-usuario/", views.PortalProvisionUserView.as_view(), name="portal-provisionar-usuario"),
    path("stock-disponible/", views.PortalStockDisponibleView.as_view(), name="portal-stock-disponible"),
    path("pedidos/", views.PortalPedidosListView.as_view(), name="portal-pedidos-list"),
    path("pedidos/crear/", views.PortalCrearPedidoView.as_view(), name="portal-crear-pedido"),
    path("pedidos/<int:pedido_id>/", views.PortalPedidoDetailView.as_view(), name="portal-pedido-detail"),
    path("pedidos/<int:pedido_id>/cancelar/", views.PortalCancelarPedidoView.as_view(), name="portal-cancelar-pedido"),
    path("documentos/", views.PortalDocumentosView.as_view(), name="portal-documentos"),
    path("estado-cuenta/", views.PortalEstadoCuentaView.as_view(), name="portal-estado-cuenta"),
]
