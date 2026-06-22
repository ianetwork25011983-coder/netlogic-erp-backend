import datetime

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import DashboardService


def _parse_fechas(request):
    hoy = datetime.date.today()
    desde_str = request.query_params.get("desde")
    hasta_str = request.query_params.get("hasta")
    fecha_desde = datetime.date.fromisoformat(desde_str) if desde_str else hoy.replace(day=1)
    fecha_hasta = datetime.date.fromisoformat(hasta_str) if hasta_str else hoy
    return fecha_desde, fecha_hasta


def _get_empresa(request):
    return request.user.empresa


class VentasResumenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        empresa = _get_empresa(request)
        if not empresa:
            return Response({"detail": "El usuario no tiene empresa asignada."}, status=status.HTTP_400_BAD_REQUEST)
        fecha_desde, fecha_hasta = _parse_fechas(request)
        return Response(DashboardService.ventas_resumen(empresa, fecha_desde, fecha_hasta))


class VentasPorPeriodoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        empresa = _get_empresa(request)
        fecha_desde, fecha_hasta = _parse_fechas(request)
        agrupacion = request.query_params.get("agrupacion", "DIA").upper()
        return Response(DashboardService.ventas_por_periodo(empresa, fecha_desde, fecha_hasta, agrupacion))


class ComparativoPeriodoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        empresa = _get_empresa(request)
        fecha_desde, fecha_hasta = _parse_fechas(request)
        return Response(DashboardService.comparativo_periodo(empresa, fecha_desde, fecha_hasta))


class TopProductosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        empresa = _get_empresa(request)
        fecha_desde, fecha_hasta = _parse_fechas(request)
        limite = int(request.query_params.get("limite", 10))
        return Response(DashboardService.top_productos_vendidos(empresa, fecha_desde, fecha_hasta, limite))


class TopClientesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        empresa = _get_empresa(request)
        fecha_desde, fecha_hasta = _parse_fechas(request)
        limite = int(request.query_params.get("limite", 10))
        return Response(DashboardService.top_clientes(empresa, fecha_desde, fecha_hasta, limite))


class ComprasResumenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        empresa = _get_empresa(request)
        fecha_desde, fecha_hasta = _parse_fechas(request)
        return Response(DashboardService.compras_resumen(empresa, fecha_desde, fecha_hasta))


class RentabilidadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        empresa = _get_empresa(request)
        fecha_desde, fecha_hasta = _parse_fechas(request)
        return Response(DashboardService.rentabilidad(empresa, fecha_desde, fecha_hasta))


class InventarioResumenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        empresa = _get_empresa(request)
        return Response(DashboardService.inventario_resumen(empresa))


class RotacionInventarioView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        empresa = _get_empresa(request)
        fecha_desde, fecha_hasta = _parse_fechas(request)
        return Response(DashboardService.rotacion_inventario(empresa, fecha_desde, fecha_hasta))


class DashboardResumenView(APIView):
    """GET /api/analytics/dashboard/ -- todos los indicadores principales en una sola llamada."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        empresa = _get_empresa(request)
        if not empresa:
            return Response({"detail": "El usuario no tiene empresa asignada."}, status=status.HTTP_400_BAD_REQUEST)
        fecha_desde, fecha_hasta = _parse_fechas(request)

        return Response({
            "periodo": {"desde": fecha_desde, "hasta": fecha_hasta},
            "ventas": DashboardService.ventas_resumen(empresa, fecha_desde, fecha_hasta),
            "compras": DashboardService.compras_resumen(empresa, fecha_desde, fecha_hasta),
            "rentabilidad": DashboardService.rentabilidad(empresa, fecha_desde, fecha_hasta),
            "inventario": DashboardService.inventario_resumen(empresa),
            "rotacion": DashboardService.rotacion_inventario(empresa, fecha_desde, fecha_hasta),
            "comparativo": DashboardService.comparativo_periodo(empresa, fecha_desde, fecha_hasta),
            "top_productos": DashboardService.top_productos_vendidos(empresa, fecha_desde, fecha_hasta, 5),
            "top_clientes": DashboardService.top_clientes(empresa, fecha_desde, fecha_hasta, 5),
        })
