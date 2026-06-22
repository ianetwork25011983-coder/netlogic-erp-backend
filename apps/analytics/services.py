"""
Módulo 13 - Dashboard Ejecutivo.

Todas las consultas son en vivo (sin tabla de caché todavía) — "tiempo
real" en el sentido de que cada llamada refleja el estado actual de la
base, no un snapshot recalculado por un cron. Un push real por
WebSocket (Channels) queda como mejora futura, igual que se documentó
para el seguimiento de Pedidos Web.

Limitación documentada: `rotacion_inventario` usa el valor de inventario
ACTUAL como aproximación del "inventario promedio del período", porque
el modelo no guarda snapshots históricos de valorización día a día.
Para una rotación exacta habría que materializar snapshots periódicos
(se puede agregar como tarea de Celery Beat más adelante).
"""
import datetime
from decimal import Decimal

from django.db.models import Count, F, Sum
from django.db.models.functions import TruncMonth, TruncWeek

from apps.billing.models import DocumentoVenta
from apps.currencies.services import CurrencyService
from apps.inventory.services import InventoryService
from apps.products.models import Producto
from apps.purchases.models import OrdenCompra


class DashboardService:
    @staticmethod
    def _facturas_qs(empresa, fecha_desde, fecha_hasta):
        return DocumentoVenta.objects.filter(
            empresa=empresa, tipo_documento=DocumentoVenta.TIPO_FACTURA, estado=DocumentoVenta.ESTADO_EMITIDA,
            fecha_emision__gte=fecha_desde, fecha_emision__lte=fecha_hasta,
        )

    @classmethod
    def ventas_resumen(cls, empresa, fecha_desde, fecha_hasta):
        qs = cls._facturas_qs(empresa, fecha_desde, fecha_hasta)
        agregado = qs.aggregate(total_pyg=Sum("total_pyg"), cantidad=Count("id"))
        total_pyg = agregado["total_pyg"] or Decimal("0")
        cantidad = agregado["cantidad"] or 0
        ticket_promedio = (total_pyg / cantidad) if cantidad else Decimal("0")

        return {
            "total_ventas_pyg": total_pyg,
            "cantidad_facturas": cantidad,
            "ticket_promedio_pyg": ticket_promedio,
        }

    @staticmethod
    def ventas_por_periodo(empresa, fecha_desde, fecha_hasta, agrupacion="DIA"):
        base_qs = DocumentoVenta.objects.filter(
            empresa=empresa, tipo_documento=DocumentoVenta.TIPO_FACTURA, estado=DocumentoVenta.ESTADO_EMITIDA,
            fecha_emision__gte=fecha_desde, fecha_emision__lte=fecha_hasta,
        )

        if agrupacion == "DIA":
            # `fecha_emision` ya es un DateField (granularidad de día), no
            # hace falta truncar — TruncDate sobre un DateField (en vez de
            # un DateTimeField) falla en SQLite, así que se evita directamente.
            qs = base_qs.values(periodo=F("fecha_emision")).annotate(total_pyg=Sum("total_pyg"), cantidad=Count("id"))
        else:
            trunc_fn = TruncWeek if agrupacion == "SEMANA" else TruncMonth
            qs = (
                base_qs.annotate(periodo=trunc_fn("fecha_emision"))
                .values("periodo")
                .annotate(total_pyg=Sum("total_pyg"), cantidad=Count("id"))
            )

        return list(qs.order_by("periodo"))

    @classmethod
    def comparativo_periodo(cls, empresa, fecha_desde, fecha_hasta):
        dias = (fecha_hasta - fecha_desde).days + 1
        fecha_hasta_anterior = fecha_desde - datetime.timedelta(days=1)
        fecha_desde_anterior = fecha_hasta_anterior - datetime.timedelta(days=dias - 1)

        actual = cls.ventas_resumen(empresa, fecha_desde, fecha_hasta)
        anterior = cls.ventas_resumen(empresa, fecha_desde_anterior, fecha_hasta_anterior)

        variacion_pct = None
        if anterior["total_ventas_pyg"] > 0:
            variacion_pct = (
                (actual["total_ventas_pyg"] - anterior["total_ventas_pyg"]) / anterior["total_ventas_pyg"] * 100
            )

        return {
            "periodo_actual": {"desde": fecha_desde, "hasta": fecha_hasta, **actual},
            "periodo_anterior": {"desde": fecha_desde_anterior, "hasta": fecha_hasta_anterior, **anterior},
            "variacion_porcentaje": variacion_pct,
        }

    @classmethod
    def top_productos_vendidos(cls, empresa, fecha_desde, fecha_hasta, limite=10):
        from apps.billing.models import DocumentoVentaItem

        qs = (
            DocumentoVentaItem.objects.filter(
                documento__empresa=empresa, documento__tipo_documento=DocumentoVenta.TIPO_FACTURA,
                documento__estado=DocumentoVenta.ESTADO_EMITIDA,
                documento__fecha_emision__gte=fecha_desde, documento__fecha_emision__lte=fecha_hasta,
            )
            .values("producto__codigo", "producto__nombre")
            .annotate(cantidad_total=Sum("cantidad"), total_linea_pyg=Sum(F("total_linea") * F("documento__tipo_cambio_pyg")))
            .order_by("-total_linea_pyg")[:limite]
        )
        return list(qs)

    @classmethod
    def top_clientes(cls, empresa, fecha_desde, fecha_hasta, limite=10):
        qs = (
            cls._facturas_qs(empresa, fecha_desde, fecha_hasta)
            .values("cliente__razon_social", "cliente__nombre_comercial")
            .annotate(total_pyg=Sum("total_pyg"), cantidad=Count("id"))
            .order_by("-total_pyg")[:limite]
        )
        return list(qs)

    @staticmethod
    def compras_resumen(empresa, fecha_desde, fecha_hasta):
        ordenes = OrdenCompra.objects.filter(
            empresa=empresa, fecha__date__gte=fecha_desde, fecha__date__lte=fecha_hasta,
        ).exclude(estado=OrdenCompra.ESTADO_CANCELADA).select_related("moneda").prefetch_related("items")

        total_pyg = Decimal("0")
        for orden in ordenes:
            total_pyg += CurrencyService.convert_to_base(orden.total, orden.moneda.code, orden.fecha.date())

        return {"total_compras_pyg": total_pyg, "cantidad_ordenes": ordenes.count()}

    @classmethod
    def rentabilidad(cls, empresa, fecha_desde, fecha_hasta):
        from apps.billing.models import DocumentoVentaItem

        items = DocumentoVentaItem.objects.filter(
            documento__empresa=empresa, documento__tipo_documento=DocumentoVenta.TIPO_FACTURA,
            documento__estado=DocumentoVenta.ESTADO_EMITIDA,
            documento__fecha_emision__gte=fecha_desde, documento__fecha_emision__lte=fecha_hasta,
        ).select_related("documento", "movimiento_inventario")

        ventas_pyg = Decimal("0")
        costo_pyg = Decimal("0")
        for item in items:
            ventas_pyg += item.subtotal_linea * item.documento.tipo_cambio_pyg
            if item.movimiento_inventario_id:
                costo_pyg += item.movimiento_inventario.costo_total_pyg

        margen_bruto_pyg = ventas_pyg - costo_pyg
        margen_pct = (margen_bruto_pyg / ventas_pyg * 100) if ventas_pyg > 0 else Decimal("0")

        return {
            "ventas_netas_pyg": ventas_pyg,
            "costo_ventas_pyg": costo_pyg,
            "margen_bruto_pyg": margen_bruto_pyg,
            "margen_porcentaje": margen_pct,
        }

    @staticmethod
    def inventario_resumen(empresa):
        saldos = InventoryService.get_valorizacion(empresa=empresa)
        valor_total_pyg = sum((s.valor_total_pyg for s in saldos), Decimal("0"))

        productos = Producto.objects.filter(empresa=empresa, active=True, tipo=Producto.TIPO_PRODUCTO)
        productos_bajo_minimo = 0
        for producto in productos:
            stock_total = sum((s.cantidad for s in producto.saldos.all()), Decimal("0"))
            if producto.stock_minimo > 0 and stock_total < producto.stock_minimo:
                productos_bajo_minimo += 1

        return {
            "valor_total_inventario_pyg": valor_total_pyg,
            "cantidad_productos_activos": productos.count(),
            "productos_bajo_stock_minimo": productos_bajo_minimo,
        }

    @classmethod
    def rotacion_inventario(cls, empresa, fecha_desde, fecha_hasta):
        rentabilidad = cls.rentabilidad(empresa, fecha_desde, fecha_hasta)
        inventario = cls.inventario_resumen(empresa)

        costo_ventas = rentabilidad["costo_ventas_pyg"]
        valor_inventario = inventario["valor_total_inventario_pyg"]
        rotacion = (costo_ventas / valor_inventario) if valor_inventario > 0 else Decimal("0")

        return {
            "costo_ventas_periodo_pyg": costo_ventas,
            "valor_inventario_actual_pyg": valor_inventario,
            "rotacion_aproximada": rotacion,
            "nota": "Aproximación usando el valor de inventario actual; no hay snapshots históricos diarios todavía.",
        }
