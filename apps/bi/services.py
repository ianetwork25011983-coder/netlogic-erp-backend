"""
Módulo 17 - Business Intelligence.

El análisis ABC sigue el principio de Pareto clásico: se ordenan los
ítems por valor descendente y se acumula el % del total que representa
cada uno; A = hasta el 80% acumulado, B = del 80% al 95%, C = el resto.
No requiere ninguna librería de "cubos OLAP" dedicada — para el volumen
de datos de una pyme, una agregación SQL directa sobre Postgres cumple
el mismo propósito sin la complejidad operativa de un motor OLAP separado.
"""
import datetime
from decimal import Decimal

from django.db.models import Sum

from apps.billing.models import DocumentoVenta


def _clasificar_abc(items, key="valor"):
    items_ordenados = sorted(items, key=lambda i: i[key], reverse=True)
    total = sum(i[key] for i in items_ordenados) or Decimal("1")
    umbral_a = total * Decimal("0.80")
    umbral_b = total * Decimal("0.95")

    acumulado_antes = Decimal("0")
    resultado = []
    for item in items_ordenados:
        # La clase se decide con el acumulado ANTES de sumar este ítem: así
        # el primer ítem (el más valioso) siempre puede ser clase A, incluso
        # si por sí solo representa más del 80% del total. Evaluar con el
        # acumulado DESPUÉS de sumarlo invertiría la clasificación en ese
        # caso (el ítem más importante terminaría en C).
        if acumulado_antes < umbral_a:
            clase = "A"
        elif acumulado_antes < umbral_b:
            clase = "B"
        else:
            clase = "C"

        acumulado_antes += item[key]
        porcentaje_acumulado = acumulado_antes / total * 100
        resultado.append({**item, "porcentaje_acumulado": round(porcentaje_acumulado, 2), "clase_abc": clase})
    return resultado


class BIService:
    @staticmethod
    def abc_productos(empresa, fecha_desde, fecha_hasta):
        from apps.billing.models import DocumentoVentaItem

        ventas = (
            DocumentoVentaItem.objects.filter(
                documento__empresa=empresa, documento__tipo_documento=DocumentoVenta.TIPO_FACTURA,
                documento__estado=DocumentoVenta.ESTADO_EMITIDA,
                documento__fecha_emision__gte=fecha_desde, documento__fecha_emision__lte=fecha_hasta,
            )
            .values("producto__id", "producto__codigo", "producto__nombre")
            .annotate(valor=Sum("total_linea"))
        )

        items = [
            {"producto_id": v["producto__id"], "codigo": v["producto__codigo"], "nombre": v["producto__nombre"], "valor": v["valor"] or Decimal("0")}
            for v in ventas
        ]
        return _clasificar_abc(items)

    @staticmethod
    def abc_clientes(empresa, fecha_desde, fecha_hasta):
        ventas = (
            DocumentoVenta.objects.filter(
                empresa=empresa, tipo_documento=DocumentoVenta.TIPO_FACTURA, estado=DocumentoVenta.ESTADO_EMITIDA,
                fecha_emision__gte=fecha_desde, fecha_emision__lte=fecha_hasta,
            )
            .values("cliente__id", "cliente__razon_social", "cliente__nombre_comercial")
            .annotate(valor=Sum("total_pyg"))
        )

        items = [
            {
                "cliente_id": v["cliente__id"], "razon_social": v["cliente__razon_social"],
                "nombre_comercial": v["cliente__nombre_comercial"], "valor": v["valor"] or Decimal("0"),
            }
            for v in ventas
        ]
        return _clasificar_abc(items)

    @staticmethod
    def clientes_en_declive(empresa, fecha_desde, fecha_hasta, umbral_caida_porcentaje=20):
        """
        Compara las compras de cada cliente en el período indicado contra
        el período inmediatamente anterior de igual duración, y devuelve
        los que cayeron más del `umbral_caida_porcentaje`.
        """
        dias = (fecha_hasta - fecha_desde).days + 1
        fecha_hasta_anterior = fecha_desde - datetime.timedelta(days=1)
        fecha_desde_anterior = fecha_hasta_anterior - datetime.timedelta(days=dias - 1)

        def totales_por_cliente(desde, hasta):
            qs = (
                DocumentoVenta.objects.filter(
                    empresa=empresa, tipo_documento=DocumentoVenta.TIPO_FACTURA, estado=DocumentoVenta.ESTADO_EMITIDA,
                    fecha_emision__gte=desde, fecha_emision__lte=hasta,
                )
                .values("cliente__id", "cliente__razon_social", "cliente__nombre_comercial")
                .annotate(total=Sum("total_pyg"))
            )
            return {v["cliente__id"]: v for v in qs}

        actual = totales_por_cliente(fecha_desde, fecha_hasta)
        anterior = totales_por_cliente(fecha_desde_anterior, fecha_hasta_anterior)

        resultado = []
        for cliente_id, datos_anterior in anterior.items():
            total_anterior = datos_anterior["total"] or Decimal("0")
            if total_anterior <= 0:
                continue
            total_actual = (actual.get(cliente_id) or {}).get("total") or Decimal("0")
            variacion_pct = (total_actual - total_anterior) / total_anterior * 100

            if variacion_pct <= -umbral_caida_porcentaje:
                resultado.append({
                    "cliente_id": cliente_id,
                    "razon_social": datos_anterior["cliente__razon_social"],
                    "nombre_comercial": datos_anterior["cliente__nombre_comercial"],
                    "total_periodo_anterior_pyg": total_anterior,
                    "total_periodo_actual_pyg": total_actual,
                    "variacion_porcentaje": round(variacion_pct, 2),
                })

        return sorted(resultado, key=lambda r: r["variacion_porcentaje"])

    @staticmethod
    def rotacion_por_categoria(empresa):
        """Valor de inventario actual agrupado por categoría, para comparar dónde está inmovilizado el capital."""
        from apps.inventory.services import InventoryService

        saldos = InventoryService.get_valorizacion(empresa=empresa).select_related("producto__categoria")
        agrupado = {}
        for saldo in saldos:
            categoria = saldo.producto.categoria.nombre if saldo.producto.categoria_id else "Sin categoría"
            registro = agrupado.setdefault(categoria, {"categoria": categoria, "valor_total_pyg": Decimal("0"), "cantidad_productos": 0})
            registro["valor_total_pyg"] += saldo.valor_total_pyg
            registro["cantidad_productos"] += 1

        return sorted(agrupado.values(), key=lambda r: r["valor_total_pyg"], reverse=True)
