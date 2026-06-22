from decimal import Decimal

import pytest

from apps.inventory.services import InsufficientStockError, InventoryError, InventoryService
from apps.products.models import Producto


@pytest.mark.django_db
class TestEntradaSalidaBasica:
    def test_entrada_crea_saldo(self, producto, deposito, user):
        mov = InventoryService.registrar_entrada(
            producto=producto, deposito=deposito, cantidad=Decimal("10"),
            costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user,
        )
        assert mov.tipo_movimiento == "ENTRADA"
        balance = producto.saldos.get(deposito=deposito, lote=None)
        assert balance.cantidad == Decimal("10")

    def test_salida_descuenta_saldo(self, producto, deposito, user):
        InventoryService.registrar_entrada(
            producto=producto, deposito=deposito, cantidad=Decimal("10"),
            costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user,
        )
        InventoryService.registrar_salida(producto=producto, deposito=deposito, cantidad=Decimal("4"), usuario=user)
        balance = producto.saldos.get(deposito=deposito, lote=None)
        assert balance.cantidad == Decimal("6")

    def test_salida_con_stock_insuficiente_lanza_excepcion(self, producto, deposito, user):
        InventoryService.registrar_entrada(
            producto=producto, deposito=deposito, cantidad=Decimal("5"),
            costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user,
        )
        with pytest.raises(InsufficientStockError):
            InventoryService.registrar_salida(producto=producto, deposito=deposito, cantidad=Decimal("999"), usuario=user)

        balance = producto.saldos.get(deposito=deposito, lote=None)
        assert balance.cantidad == Decimal("5")  # no se modificó por el rollback

    def test_entrada_en_moneda_distinta_se_convierte_a_pyg(self, producto, deposito, user, usd):
        mov = InventoryService.registrar_entrada(
            producto=producto, deposito=deposito, cantidad=Decimal("10"),
            costo_unitario=Decimal("100"), moneda_costo_code="USD", usuario=user,
        )
        assert mov.costo_unitario_pyg == Decimal("750000.000000")


@pytest.mark.django_db
class TestCosteoFIFO:
    def test_fifo_consume_capas_en_orden(self, empresa, unidad_medida, pyg, deposito, user):
        producto = Producto.objects.create(
            empresa=empresa, tipo=Producto.TIPO_PRODUCTO, codigo="P-FIFO", nombre="Producto FIFO",
            unidad_medida=unidad_medida, moneda_costo=pyg, moneda_precio=pyg, metodo_costeo=Producto.METODO_FIFO,
        )
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("1200"), moneda_costo_code="PYG", usuario=user)
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("1500"), moneda_costo_code="PYG", usuario=user)

        salida = InventoryService.registrar_salida(producto=producto, deposito=deposito, cantidad=Decimal("15"), usuario=user)
        assert salida.costo_total_pyg == Decimal("16000.00")
        assert salida.costo_unitario_pyg == Decimal("1066.666667")


@pytest.mark.django_db
class TestCosteoLIFO:
    def test_lifo_consume_capas_mas_recientes_primero(self, empresa, unidad_medida, pyg, deposito, user):
        producto = Producto.objects.create(
            empresa=empresa, tipo=Producto.TIPO_PRODUCTO, codigo="P-LIFO", nombre="Producto LIFO",
            unidad_medida=unidad_medida, moneda_costo=pyg, moneda_precio=pyg, metodo_costeo=Producto.METODO_LIFO,
        )
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("1500"), moneda_costo_code="PYG", usuario=user)

        salida = InventoryService.registrar_salida(producto=producto, deposito=deposito, cantidad=Decimal("5"), usuario=user)
        assert salida.costo_unitario_pyg == Decimal("1500.000000")


@pytest.mark.django_db
class TestCosteoPromedio:
    def test_promedio_ponderado_se_recalcula_en_cada_entrada(self, producto, deposito, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("2000"), moneda_costo_code="PYG", usuario=user)

        balance = producto.saldos.get(deposito=deposito, lote=None)
        assert balance.costo_promedio_pyg == Decimal("1500.000000")

        salida = InventoryService.registrar_salida(producto=producto, deposito=deposito, cantidad=Decimal("5"), usuario=user)
        assert salida.costo_unitario_pyg == Decimal("1500.000000")
        balance.refresh_from_db()
        assert balance.costo_promedio_pyg == Decimal("1500.000000")


@pytest.mark.django_db
class TestTransferencia:
    def test_transferencia_mantiene_el_mismo_costo(self, producto, deposito, deposito_b, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("20"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)

        mov_salida, mov_entrada = InventoryService.registrar_transferencia(
            producto=producto, deposito_origen=deposito, deposito_destino=deposito_b, cantidad=Decimal("8"), usuario=user,
        )
        assert mov_salida.costo_unitario_pyg == mov_entrada.costo_unitario_pyg == Decimal("1000.000000")
        assert mov_salida.grupo_transferencia == mov_entrada.grupo_transferencia

        assert producto.saldos.get(deposito=deposito, lote=None).cantidad == Decimal("12")
        assert producto.saldos.get(deposito=deposito_b, lote=None).cantidad == Decimal("8")

    def test_no_se_puede_transferir_al_mismo_deposito(self, producto, deposito, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)
        with pytest.raises(InventoryError):
            InventoryService.registrar_transferencia(
                producto=producto, deposito_origen=deposito, deposito_destino=deposito, cantidad=Decimal("5"), usuario=user,
            )


@pytest.mark.django_db
class TestAjusteYConteo:
    def test_ajuste_positivo_incrementa_stock(self, producto, deposito, user):
        ajuste = InventoryService.registrar_ajuste(
            producto=producto, deposito=deposito, cantidad_ajuste=Decimal("5"), motivo="Sobrante", usuario=user,
        )
        assert ajuste.tipo_movimiento == "AJUSTE_POSITIVO"
        assert producto.saldos.get(deposito=deposito, lote=None).cantidad == Decimal("5")

    def test_ajuste_negativo_decrementa_stock(self, producto, deposito, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)
        ajuste = InventoryService.registrar_ajuste(
            producto=producto, deposito=deposito, cantidad_ajuste=Decimal("-3"), motivo="Faltante", usuario=user,
        )
        assert ajuste.tipo_movimiento == "AJUSTE_NEGATIVO"
        assert producto.saldos.get(deposito=deposito, lote=None).cantidad == Decimal("7")

    def test_conteo_fisico_genera_ajuste_por_diferencia(self, producto, deposito, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)
        conteo = InventoryService.registrar_conteo_fisico(
            producto=producto, deposito=deposito, cantidad_contada=Decimal("8"), usuario=user,
        )
        assert conteo.tipo_movimiento == "AJUSTE_NEGATIVO"
        assert conteo.cantidad == Decimal("2")

    def test_conteo_fisico_sin_diferencia_no_genera_movimiento(self, producto, deposito, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)
        conteo = InventoryService.registrar_conteo_fisico(
            producto=producto, deposito=deposito, cantidad_contada=Decimal("10"), usuario=user,
        )
        assert conteo is None


@pytest.mark.django_db
class TestReservas:
    def test_reservar_stock_resta_de_disponible(self, producto, deposito, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("20"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)
        InventoryService.reservar_stock(producto=producto, deposito=deposito, cantidad=Decimal("5"), referencia_tipo="TEST", referencia_id=1)

        disponible = InventoryService.cantidad_disponible_venta(producto, deposito)
        assert disponible == Decimal("15")

    def test_reservar_mas_de_lo_disponible_falla(self, producto, deposito, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("5"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)
        with pytest.raises(InsufficientStockError):
            InventoryService.reservar_stock(producto=producto, deposito=deposito, cantidad=Decimal("999"), referencia_tipo="TEST", referencia_id=1)

    def test_liberar_reserva_restaura_disponibilidad(self, producto, deposito, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("20"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)
        InventoryService.reservar_stock(producto=producto, deposito=deposito, cantidad=Decimal("5"), referencia_tipo="TEST", referencia_id=42)
        InventoryService.liberar_reservas_de_referencia("TEST", 42)

        disponible = InventoryService.cantidad_disponible_venta(producto, deposito)
        assert disponible == Decimal("20")


@pytest.mark.django_db
class TestKardexYValorizacion:
    def test_kardex_devuelve_movimientos_ordenados(self, producto, deposito, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)
        InventoryService.registrar_salida(producto=producto, deposito=deposito, cantidad=Decimal("3"), usuario=user)

        kardex = list(InventoryService.get_kardex(producto, deposito=deposito))
        assert len(kardex) == 2
        assert kardex[0].tipo_movimiento == "ENTRADA"
        assert kardex[1].tipo_movimiento == "SALIDA"

    def test_valorizacion_excluye_saldos_en_cero(self, producto, deposito, user, empresa):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)
        InventoryService.registrar_salida(producto=producto, deposito=deposito, cantidad=Decimal("10"), usuario=user)

        saldos = InventoryService.get_valorizacion(empresa=empresa)
        assert saldos.count() == 0
