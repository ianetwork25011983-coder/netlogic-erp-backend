import datetime

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import BIService


def _parse_fechas(request):
    hoy = datetime.date.today()
    desde_str = request.query_params.get("desde")
    hasta_str = request.query_params.get("hasta")
    fecha_desde = datetime.date.fromisoformat(desde_str) if desde_str else hoy.replace(day=1)
    fecha_hasta = datetime.date.fromisoformat(hasta_str) if hasta_str else hoy
    return fecha_desde, fecha_hasta


class AbcProductosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        fecha_desde, fecha_hasta = _parse_fechas(request)
        return Response(BIService.abc_productos(request.user.empresa, fecha_desde, fecha_hasta))


class AbcClientesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        fecha_desde, fecha_hasta = _parse_fechas(request)
        return Response(BIService.abc_clientes(request.user.empresa, fecha_desde, fecha_hasta))


class ClientesEnDeclive(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        fecha_desde, fecha_hasta = _parse_fechas(request)
        umbral = int(request.query_params.get("umbral", 20))
        return Response(BIService.clientes_en_declive(request.user.empresa, fecha_desde, fecha_hasta, umbral))


class RotacionPorCategoriaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(BIService.rotacion_por_categoria(request.user.empresa))
