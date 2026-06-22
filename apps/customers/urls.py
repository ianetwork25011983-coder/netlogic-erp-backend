from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("clientes", views.ClienteViewSet, basename="cliente")

urlpatterns = router.urls
