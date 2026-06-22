from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("listas-precio", views.ListaPrecioViewSet, basename="listaprecio")
router.register("promociones", views.PromocionViewSet, basename="promocion")
router.register("cupones", views.CuponViewSet, basename="cupon")

urlpatterns = router.urls
