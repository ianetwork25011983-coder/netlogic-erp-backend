from rest_framework.routers import DefaultRouter

from django.urls import path

from . import views

router = DefaultRouter()
router.register("solicitudes", views.SolicitudCompraViewSet, basename="solicitudcompra")
router.register("cotizaciones", views.CotizacionViewSet, basename="cotizacion")
router.register("ordenes", views.OrdenCompraViewSet, basename="ordencompra")
router.register("recepciones", views.RecepcionCompraViewSet, basename="recepcioncompra")
router.register("facturas-proveedor", views.FacturaProveedorViewSet, basename="facturaproveedor")

urlpatterns = [
    path(
        "solicitudes/<int:solicitud_id>/comparar-cotizaciones/",
        views.CompararCotizacionesView.as_view(),
        name="comparar-cotizaciones",
    ),
    path(
        "cotizaciones/<int:cotizacion_id>/crear-orden/",
        views.CrearOrdenDesdeCotizacionView.as_view(),
        name="crear-orden-desde-cotizacion",
    ),
    path("ordenes/recibir/", views.RecibirOrdenCompraView.as_view(), name="recibir-orden-compra"),
    path(
        "proveedores/<int:proveedor_id>/historial/",
        views.HistorialProveedorView.as_view(),
        name="historial-proveedor",
    ),
] + router.urls
