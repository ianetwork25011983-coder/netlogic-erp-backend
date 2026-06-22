from django.urls import path

from . import views

urlpatterns = [
    path("preguntar/", views.PreguntarView.as_view(), name="copilot-preguntar"),
    path("historial/", views.HistorialConsultasView.as_view(), name="copilot-historial"),
]
