from rest_framework.routers import DefaultRouter

from django.urls import path

from . import views

router = DefaultRouter()
router.register("cajas", views.CajaViewSet, basename="caja")
router.register("aperturas", views.AperturaCajaViewSet, basename="aperturacaja")
router.register("bancos", views.BancoViewSet, basename="banco")
router.register("cuentas-bancarias", views.CuentaBancariaViewSet, basename="cuentabancaria")
router.register("movimientos-bancarios", views.MovimientoBancarioViewSet, basename="movimientobancario")

urlpatterns = [
    path("cajas/abrir/", views.AbrirCajaView.as_view(), name="abrir-caja"),
    path("aperturas/<int:apertura_id>/cerrar/", views.CerrarCajaView.as_view(), name="cerrar-caja"),
    path("movimientos/registrar/", views.RegistrarMovimientoCajaView.as_view(), name="registrar-movimiento-caja"),
    path("movimientos/cobro-factura/", views.CobroFacturaView.as_view(), name="cobro-factura"),
    path("movimientos/pago-proveedor/", views.PagoProveedorView.as_view(), name="pago-proveedor"),
    path(
        "movimientos-bancarios/registrar/",
        views.RegistrarMovimientoBancarioView.as_view(),
        name="registrar-movimiento-bancario",
    ),
] + router.urls
