from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("proveedores", views.ProveedorViewSet, basename="proveedor")

urlpatterns = router.urls
