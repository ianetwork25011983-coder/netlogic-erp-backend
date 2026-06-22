from rest_framework.routers import DefaultRouter

from django.urls import path

from . import views

router = DefaultRouter()
router.register("transportistas", views.TransportistaViewSet, basename="transportista")
router.register("vehiculos", views.VehiculoViewSet, basename="vehiculo")
router.register("rutas", views.RutaViewSet, basename="ruta")
router.register("ordenes-picking", views.OrdenPickingViewSet, basename="ordenpicking")
router.register("despachos", views.DespachoViewSet, basename="despacho")

urlpatterns = [
    path("picking/iniciar/", views.IniciarPickingView.as_view(), name="iniciar-picking"),
    path("picking/<int:orden_picking_id>/completar/", views.CompletarPickingView.as_view(), name="completar-picking"),
    path("picking/<int:orden_picking_id>/packing/", views.CrearPackingView.as_view(), name="crear-packing"),
    path("despachos/crear/", views.CrearDespachoView.as_view(), name="crear-despacho"),
    path(
        "despacho-documentos/<int:despacho_documento_id>/entrega/",
        views.RegistrarEntregaView.as_view(),
        name="registrar-entrega",
    ),
] + router.urls
