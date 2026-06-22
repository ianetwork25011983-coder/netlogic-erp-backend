import calendar
import datetime
from decimal import Decimal

import pytest

from apps.ai_engine.services import InventoryAIService
from apps.billing.models import DocumentoVenta
from apps.billing.services import BillingService
from apps.inventory.services import InventoryService


def _primer_dia_hace_n_meses(n):
    hoy = datetime.date.today()
    mes = hoy.month - n
    anio = hoy.year
    while mes <= 0:
        mes += 12
        anio -= 1
    return datetime.date(anio, mes, min(hoy.day, calendar.monthrange(anio, mes)[1]))


@pytest.mark.django_db
class TestProyeccionDemanda:
    def test_proyeccion_detecta_tendencia_creciente(self, empresa, sucursal, punto_venta, cliente, producto, deposito, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("1000"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)

        for i, cantidad in enumerate(reversed([10, 12, 15, 18])):
            meses_atras = 3 - i
            BillingService.emitir_documento(
                empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
                cliente=cliente, moneda_code="PYG",
                items_data=[{"producto_id": producto.id, "cantidad": Decimal(cantidad), "precio_unitario": Decimal("100000")}],
                usuario=user, fecha_emision=_primer_dia_hace_n_meses(meses_atras),
            )

        proyeccion = InventoryAIService.proyeccion_demanda_mensual(producto, meses_adelante=1)
        assert proyeccion["metodo"] == "promedio_movil_con_tendencia_lineal"
        assert proyeccion["tendencia_mensual"] > 0

    def test_sin_ventas_la_proyeccion_es_plana_en_cero(self, producto):
        proyeccion = InventoryAIService.proyeccion_demanda_mensual(producto)
        assert proyeccion["metodo"] == "promedio_movil_con_tendencia_lineal"
        assert proyeccion["proyeccion"] == 0.0
        assert proyeccion["tendencia_mensual"] == 0.0

    def test_con_un_solo_mes_de_historial_devuelve_insuficiente(self, producto):
        proyeccion = InventoryAIService.proyeccion_demanda_mensual(producto, meses_historial=0)
        assert proyeccion["metodo"] == "insuficiente_historial"


@pytest.mark.django_db
class TestReposicionInteligente:
    def test_productos_para_reponer_detecta_stock_bajo_minimo(self, empresa, deposito, producto, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("5"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        resultado = InventoryAIService.productos_para_reponer(empresa)
        assert any(r["codigo"] == producto.codigo for r in resultado)

    def test_sugerir_stock_minimo_maximo_devuelve_valores_no_negativos(self, producto):
        sugerencia = InventoryAIService.sugerir_stock_minimo_maximo(producto)
        assert sugerencia["stock_minimo_sugerido"] >= 0
        assert sugerencia["stock_maximo_sugerido"] >= sugerencia["stock_minimo_sugerido"]

    def test_generar_orden_compra_sugerida_agrupa_por_proveedor(self, empresa, sucursal, deposito, producto, proveedor, user):
        producto.proveedor_principal = proveedor
        producto.save()
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("2"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)

        ordenes = InventoryAIService.generar_orden_compra_sugerida(empresa, sucursal, user)
        assert len(ordenes) == 1
        assert ordenes[0].proveedor == proveedor
        assert ordenes[0].items.count() == 1


@pytest.mark.django_db
class TestAnomalias:
    def test_productos_sobre_stock_detecta_exceso(self, empresa, deposito, producto, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("500"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)
        resultado = InventoryAIService.productos_sobre_stock(empresa)
        assert any(r["codigo"] == producto.codigo for r in resultado)

    def test_productos_criticos_detecta_stock_en_cero(self, empresa, producto):
        resultado = InventoryAIService.productos_criticos(empresa)
        assert any(r["codigo"] == producto.codigo for r in resultado)

    def test_productos_rotacion_lenta_detecta_sin_salidas(self, empresa, deposito, producto, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)
        resultado = InventoryAIService.productos_rotacion_lenta(empresa, dias=90)
        assert any(r["codigo"] == producto.codigo for r in resultado)

    def test_alertas_preventivas_consolida_las_cuatro_categorias(self, empresa, deposito, producto, user):
        resultado = InventoryAIService.alertas_preventivas(empresa)
        assert set(resultado.keys()) == {
            "productos_criticos", "productos_para_reponer", "productos_sobre_stock", "productos_rotacion_lenta",
        }


@pytest.mark.django_db
class TestSugerirTransferencias:
    def test_sugiere_transferencia_de_deposito_con_exceso_a_deposito_con_faltante(self, empresa, deposito, deposito_b, producto, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("5"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)
        InventoryService.registrar_entrada(producto=producto, deposito=deposito_b, cantidad=Decimal("150"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)

        sugerencias = InventoryAIService.sugerir_transferencias(empresa)
        assert len(sugerencias) >= 1
        assert sugerencias[0]["deposito_origen_id"] == deposito_b.id
        assert sugerencias[0]["deposito_destino_id"] == deposito.id
