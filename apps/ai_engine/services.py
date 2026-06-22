"""
Módulo 5 - Inteligencia Artificial de Inventario.

Decisión de diseño deliberada: esto usa métodos estadísticos clásicos
(promedio móvil, tendencia lineal simple, desviación estándar para el
stock de seguridad) en lugar de un modelo de Machine Learning entrenado.
Es el punto de partida realista para "IA de inventario" en un ERP nuevo
sin años de datos históricos todavía, y no depende de librerías de ML
pesadas (numpy/scikit-learn) ni de un proceso de entrenamiento/MLOps.
Si en el futuro hay suficiente histórico (2+ años) y se justifica la
complejidad, este servicio es el punto de extensión natural para
incorporar un modelo real (ej. Prophet, statsmodels SARIMA) sin cambiar
los métodos que ya consumen `InventoryAIService` (Dashboard, Copiloto).
"""
import datetime
import statistics
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.billing.models import DocumentoVenta, DocumentoVentaItem
from apps.inventory.models import MovimientoInventario
from apps.products.models import Producto


class InventoryAIService:
    @staticmethod
    def historial_ventas_mensual(producto, meses=12):
        """Cantidad vendida por mes, últimos `meses` meses (incluye meses sin ventas como 0)."""
        hoy = datetime.date.today()
        desde = (hoy.replace(day=1) - datetime.timedelta(days=30 * meses)).replace(day=1)

        ventas = (
            DocumentoVentaItem.objects.filter(
                producto=producto, documento__tipo_documento=DocumentoVenta.TIPO_FACTURA,
                documento__estado=DocumentoVenta.ESTADO_EMITIDA, documento__fecha_emision__gte=desde,
            )
            .annotate(mes=TruncMonth("documento__fecha_emision"))
            .values("mes")
            .annotate(cantidad=Sum("cantidad"))
        )
        por_mes = {v["mes"]: float(v["cantidad"]) for v in ventas}

        resultado = []
        cursor = desde
        while cursor <= hoy.replace(day=1):
            resultado.append({"mes": cursor, "cantidad": por_mes.get(cursor, 0.0)})
            cursor = (cursor.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        return resultado

    @classmethod
    def promedio_movil_mensual(cls, producto, meses=3):
        historial = cls.historial_ventas_mensual(producto, meses=meses)
        cantidades = [h["cantidad"] for h in historial[-meses:]]
        return statistics.mean(cantidades) if cantidades else 0.0

    @classmethod
    def proyeccion_demanda_mensual(cls, producto, meses_adelante=1, meses_historial=6):
        """
        Proyección simple: promedio móvil + ajuste de tendencia lineal
        (pendiente de los últimos `meses_historial` meses) extrapolado
        `meses_adelante` meses hacia adelante. No usa estacionalidad si
        hay menos de 24 meses de historial (no hay suficiente dato para
        comparar el mismo mes en años distintos).
        """
        historial = cls.historial_ventas_mensual(producto, meses=meses_historial)
        cantidades = [h["cantidad"] for h in historial]

        if len(cantidades) < 2:
            return {"proyeccion": cantidades[-1] if cantidades else 0.0, "metodo": "insuficiente_historial"}

        n = len(cantidades)
        x_vals = list(range(n))
        x_mean = statistics.mean(x_vals)
        y_mean = statistics.mean(cantidades)
        numerador = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, cantidades))
        denominador = sum((x - x_mean) ** 2 for x in x_vals)
        pendiente = numerador / denominador if denominador else 0.0

        proyeccion = y_mean + pendiente * ((n - 1 + meses_adelante) - x_mean)
        proyeccion = max(proyeccion, 0.0)

        return {
            "proyeccion": round(proyeccion, 2),
            "promedio_historico": round(y_mean, 2),
            "tendencia_mensual": round(pendiente, 2),
            "metodo": "promedio_movil_con_tendencia_lineal",
        }

    @classmethod
    def prediccion_mensual(cls, producto, meses_adelante=3):
        """Predicción mes a mes para los próximos `meses_adelante` meses."""
        base = cls.historial_ventas_mensual(producto, meses=6)
        predicciones = []
        hoy = datetime.date.today().replace(day=1)
        for i in range(1, meses_adelante + 1):
            mes_objetivo = (hoy.replace(day=28) + datetime.timedelta(days=31 * i)).replace(day=1)
            proy = cls.proyeccion_demanda_mensual(producto, meses_adelante=i, meses_historial=len(base))
            predicciones.append({"mes": mes_objetivo, **proy})
        return predicciones

    @classmethod
    def sugerir_stock_minimo_maximo(cls, producto, lead_time_dias=7, dias_ciclo_pedido=30, nivel_servicio_z=1.65):
        """
        `nivel_servicio_z` = 1.65 corresponde aproximadamente a un 95% de
        nivel de servicio asumiendo demanda con distribución normal —
        una simplificación estándar en gestión de inventario clásica.
        """
        historial = cls.historial_ventas_mensual(producto, meses=6)
        cantidades_mensuales = [h["cantidad"] for h in historial]

        demanda_diaria_promedio = (statistics.mean(cantidades_mensuales) / 30) if cantidades_mensuales else 0.0
        desviacion_mensual = statistics.stdev(cantidades_mensuales) if len(cantidades_mensuales) >= 2 else 0.0
        desviacion_diaria = desviacion_mensual / 30

        stock_seguridad = nivel_servicio_z * desviacion_diaria * (lead_time_dias ** 0.5)
        stock_minimo = demanda_diaria_promedio * lead_time_dias + stock_seguridad
        stock_maximo = stock_minimo + demanda_diaria_promedio * dias_ciclo_pedido
        punto_reposicion = stock_minimo

        return {
            "demanda_diaria_promedio": round(demanda_diaria_promedio, 3),
            "stock_seguridad_sugerido": round(stock_seguridad, 2),
            "stock_minimo_sugerido": round(stock_minimo, 2),
            "stock_maximo_sugerido": round(stock_maximo, 2),
            "punto_reposicion_sugerido": round(punto_reposicion, 2),
        }

    @staticmethod
    def _stock_actual(producto, deposito=None):
        qs = producto.saldos.all()
        if deposito is not None:
            qs = qs.filter(deposito=deposito)
        return sum((s.cantidad for s in qs), Decimal("0"))

    @classmethod
    def productos_para_reponer(cls, empresa, deposito=None):
        """Productos cuyo stock actual está en o por debajo de su stock mínimo configurado."""
        resultado = []
        productos = Producto.objects.filter(empresa=empresa, active=True, tipo=Producto.TIPO_PRODUCTO)
        for producto in productos:
            if producto.stock_minimo <= 0:
                continue
            stock_actual = cls._stock_actual(producto, deposito)
            if stock_actual <= producto.stock_minimo:
                cantidad_sugerida = max(producto.stock_maximo - stock_actual, producto.stock_minimo)
                resultado.append({
                    "producto_id": producto.id, "codigo": producto.codigo, "nombre": producto.nombre,
                    "stock_actual": stock_actual, "stock_minimo": producto.stock_minimo,
                    "stock_maximo": producto.stock_maximo, "cantidad_sugerida_compra": cantidad_sugerida,
                    "proveedor_principal_id": producto.proveedor_principal_id,
                })
        return sorted(resultado, key=lambda r: r["stock_actual"])

    @classmethod
    def productos_sobre_stock(cls, empresa):
        resultado = []
        for producto in Producto.objects.filter(empresa=empresa, active=True, tipo=Producto.TIPO_PRODUCTO, stock_maximo__gt=0):
            stock_actual = cls._stock_actual(producto)
            if stock_actual > producto.stock_maximo:
                resultado.append({
                    "producto_id": producto.id, "codigo": producto.codigo, "nombre": producto.nombre,
                    "stock_actual": stock_actual, "stock_maximo": producto.stock_maximo,
                    "exceso": stock_actual - producto.stock_maximo,
                })
        return sorted(resultado, key=lambda r: r["exceso"], reverse=True)

    @classmethod
    def productos_rotacion_lenta(cls, empresa, dias=90):
        """Productos con stock > 0 que no tuvieron ninguna SALIDA en los últimos `dias` días."""
        limite = timezone.now() - datetime.timedelta(days=dias)
        resultado = []
        for producto in Producto.objects.filter(empresa=empresa, active=True, tipo=Producto.TIPO_PRODUCTO):
            stock_actual = cls._stock_actual(producto)
            if stock_actual <= 0:
                continue
            ultima_salida = MovimientoInventario.objects.filter(
                producto=producto, tipo_movimiento=MovimientoInventario.TIPO_SALIDA,
            ).order_by("-fecha").first()
            if ultima_salida is None or ultima_salida.fecha < limite:
                resultado.append({
                    "producto_id": producto.id, "codigo": producto.codigo, "nombre": producto.nombre,
                    "stock_actual": stock_actual,
                    "ultima_salida": ultima_salida.fecha if ultima_salida else None,
                })
        return resultado

    @classmethod
    def productos_obsoletos(cls, empresa, dias=180):
        """Productos con stock > 0 sin NINGÚN movimiento (entrada o salida) en `dias` días."""
        limite = timezone.now() - datetime.timedelta(days=dias)
        resultado = []
        for producto in Producto.objects.filter(empresa=empresa, active=True, tipo=Producto.TIPO_PRODUCTO):
            stock_actual = cls._stock_actual(producto)
            if stock_actual <= 0:
                continue
            ultimo_movimiento = MovimientoInventario.objects.filter(producto=producto).order_by("-fecha").first()
            if ultimo_movimiento is None or ultimo_movimiento.fecha < limite:
                resultado.append({
                    "producto_id": producto.id, "codigo": producto.codigo, "nombre": producto.nombre,
                    "stock_actual": stock_actual,
                    "ultimo_movimiento": ultimo_movimiento.fecha if ultimo_movimiento else None,
                })
        return resultado

    @classmethod
    def productos_criticos(cls, empresa):
        """Productos en stock 0 o negativo lógico (agotados) — máxima urgencia de reposición."""
        resultado = []
        for producto in Producto.objects.filter(empresa=empresa, active=True, tipo=Producto.TIPO_PRODUCTO):
            stock_actual = cls._stock_actual(producto)
            if stock_actual <= 0:
                resultado.append({
                    "producto_id": producto.id, "codigo": producto.codigo, "nombre": producto.nombre,
                    "stock_actual": stock_actual,
                })
        return resultado

    @classmethod
    def alertas_preventivas(cls, empresa):
        """Resumen consolidado para un panel de alertas: críticos, a reponer, sobre stock y rotación lenta."""
        return {
            "productos_criticos": cls.productos_criticos(empresa),
            "productos_para_reponer": cls.productos_para_reponer(empresa),
            "productos_sobre_stock": cls.productos_sobre_stock(empresa),
            "productos_rotacion_lenta": cls.productos_rotacion_lenta(empresa),
        }

    # ------------------------------------------------------------------
    # Sugerencias automáticas: transferencias y compras
    # ------------------------------------------------------------------
    @classmethod
    def sugerir_transferencias(cls, empresa):
        """
        Para cada producto, si un depósito tiene stock por encima de su
        máximo y otro depósito del mismo producto está en su mínimo o
        por debajo, sugiere transferir el excedente (o lo que haga falta,
        lo que sea menor) del primero al segundo.
        """
        from apps.companies.models import Deposito

        sugerencias = []
        depositos = list(Deposito.objects.filter(sucursal__empresa=empresa, active=True))
        productos = Producto.objects.filter(empresa=empresa, active=True, tipo=Producto.TIPO_PRODUCTO).filter(
            stock_minimo__gt=0
        )

        for producto in productos:
            saldos_por_deposito = {s.deposito_id: s.cantidad for s in producto.saldos.filter(lote=None)}
            sobrantes = []
            faltantes = []
            for deposito in depositos:
                cantidad = saldos_por_deposito.get(deposito.id, Decimal("0"))
                if producto.stock_maximo > 0 and cantidad > producto.stock_maximo:
                    sobrantes.append((deposito, cantidad - producto.stock_maximo))
                elif cantidad <= producto.stock_minimo:
                    faltantes.append((deposito, producto.stock_minimo - cantidad))

            for deposito_origen, excedente in sobrantes:
                for deposito_destino, faltante in faltantes:
                    if deposito_origen.id == deposito_destino.id:
                        continue
                    cantidad_a_transferir = min(excedente, faltante)
                    if cantidad_a_transferir > 0:
                        sugerencias.append({
                            "producto_id": producto.id, "codigo": producto.codigo, "nombre": producto.nombre,
                            "deposito_origen_id": deposito_origen.id, "deposito_origen": str(deposito_origen),
                            "deposito_destino_id": deposito_destino.id, "deposito_destino": str(deposito_destino),
                            "cantidad_sugerida": cantidad_a_transferir,
                        })
        return sugerencias

    @classmethod
    def generar_orden_compra_sugerida(cls, empresa, sucursal, usuario, proveedor=None):
        """
        Agrupa `productos_para_reponer` por proveedor principal y crea
        una Orden de Compra en estado BORRADOR por proveedor (usando el
        costo actual del producto como precio estimado — el comprador
        la revisa y ajusta antes de enviarla). Devuelve la lista de
        órdenes creadas.
        """
        from collections import defaultdict

        from apps.purchases.models import OrdenCompra, OrdenCompraItem
        from apps.purchases.services import PurchaseService

        candidatos = cls.productos_para_reponer(empresa)
        por_proveedor = defaultdict(list)
        for item in candidatos:
            proveedor_id = item["proveedor_principal_id"]
            if proveedor_id is None:
                continue
            if proveedor is not None and proveedor_id != proveedor.id:
                continue
            por_proveedor[proveedor_id].append(item)

        ordenes_creadas = []
        for proveedor_id, items in por_proveedor.items():
            primer_producto = Producto.objects.get(pk=items[0]["producto_id"])
            proveedor_obj = primer_producto.proveedor_principal

            orden = OrdenCompra.objects.create(
                empresa=empresa, sucursal=sucursal, proveedor=proveedor_obj,
                numero=PurchaseService.generar_numero_orden_compra(empresa),
                moneda=proveedor_obj.moneda_default, usuario=usuario,
                observaciones="Generada automáticamente por sugerencia de reposición (IA de Inventario).",
            )
            for item in items:
                producto = Producto.objects.get(pk=item["producto_id"])
                OrdenCompraItem.objects.create(
                    orden_compra=orden, producto=producto, cantidad=item["cantidad_sugerida_compra"],
                    precio_unitario=producto.costo,
                )
            ordenes_creadas.append(orden)

        return ordenes_creadas
