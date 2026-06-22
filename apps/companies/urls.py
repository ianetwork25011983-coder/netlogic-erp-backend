from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("empresas", views.EmpresaViewSet, basename="empresa")
router.register("sucursales", views.SucursalViewSet, basename="sucursal")
router.register("depositos", views.DepositoViewSet, basename="deposito")
router.register("puntos-venta", views.PuntoVentaViewSet, basename="puntoventa")

urlpatterns = router.urls
