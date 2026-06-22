from rest_framework.routers import DefaultRouter

from django.urls import path

from . import views

router = DefaultRouter()
router.register("ubicaciones", views.UbicacionViewSet, basename="ubicacion")
router.register("saldos", views.StockBalanceViewSet, basename="stockbalance")
router.register("reservas", views.StockReservaViewSet, basename="stockreserva")
router.register("capas-costo", views.CapaCostoViewSet, basename="capacosto")
router.register("movimientos", views.MovimientoInventarioViewSet, basename="movimientoinventario")

urlpatterns = [
    path("movimientos/entrada/", views.EntradaInventarioView.as_view(), name="inventario-entrada"),
    path("movimientos/salida/", views.SalidaInventarioView.as_view(), name="inventario-salida"),
    path("movimientos/transferencia/", views.TransferenciaInventarioView.as_view(), name="inventario-transferencia"),
    path("movimientos/ajuste/", views.AjusteInventarioView.as_view(), name="inventario-ajuste"),
    path("movimientos/conteo-fisico/", views.ConteoFisicoInventarioView.as_view(), name="inventario-conteo-fisico"),
    path("kardex/", views.KardexView.as_view(), name="inventario-kardex"),
    path("valorizacion/", views.ValorizacionInventarioView.as_view(), name="inventario-valorizacion"),
] + router.urls
