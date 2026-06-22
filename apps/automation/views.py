from django.shortcuts import get_object_or_404
from rest_framework import permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Alerta, EjecucionRegla, ReglaAutomatizacion
from .serializers import (
    AlertaSerializer,
    EjecucionReglaSerializer,
    EvaluarPedidoInputSerializer,
    EvaluarProductoInputSerializer,
    ReglaAutomatizacionSerializer,
)
from .services import RuleEngineService


class ScopedToEmpresaMixin:
    empresa_lookup = "empresa"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(**{self.empresa_lookup: user.empresa})


class ReglaAutomatizacionViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = ReglaAutomatizacion.objects.select_related("empresa")
    serializer_class = ReglaAutomatizacionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["tipo_entidad", "evaluar_en", "accion", "active"]


class AlertaViewSet(ScopedToEmpresaMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Alerta.objects.select_related("empresa", "regla")
    serializer_class = AlertaSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["leida"]


class MarcarAlertaLeidaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, alerta_id):
        qs = Alerta.objects.all() if request.user.is_superuser else Alerta.objects.filter(empresa=request.user.empresa)
        alerta = get_object_or_404(qs, pk=alerta_id)
        alerta.leida = True
        alerta.save(update_fields=["leida"])
        return Response(AlertaSerializer(alerta).data)


class EjecucionReglaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EjecucionRegla.objects.select_related("regla")
    serializer_class = EjecucionReglaSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["regla", "condicion_cumplida"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_superuser:
            qs = qs.filter(regla__empresa=user.empresa)
        return qs


class EvaluarProductoView(APIView):
    """POST /api/automation/evaluar/producto/ {"producto_id": <id>} -- evalúa manualmente las reglas AL_GUARDAR de un producto."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.products.models import Producto

        serializer = EvaluarProductoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        producto = get_object_or_404(Producto, pk=serializer.validated_data["producto_id"])

        resultados = RuleEngineService.evaluar_producto(producto)
        return Response({"resultados": resultados})


class EvaluarPedidoWebView(APIView):
    """POST /api/automation/evaluar/pedido-web/ {"pedido_web_id": <id>}"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.orders.models import PedidoWeb

        serializer = EvaluarPedidoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pedido = get_object_or_404(PedidoWeb, pk=serializer.validated_data["pedido_web_id"])

        resultados = RuleEngineService.evaluar_pedido_web(pedido)
        return Response({"resultados": resultados})
