import datetime
from decimal import Decimal

import pytest

from apps.pricing.models import Cupon, ListaPrecio, PrecioProducto, Promocion


@pytest.mark.django_db
class TestCupon:
    def test_cupon_porcentual_calcula_descuento(self, empresa):
        cupon = Cupon.objects.create(
            empresa=empresa, codigo="DESC10", tipo_descuento=Cupon.TIPO_PORCENTAJE, valor=Decimal("10"),
            vigencia_desde=datetime.date.today(), vigencia_hasta=datetime.date.today() + datetime.timedelta(days=30),
        )
        assert cupon.calcular_descuento(Decimal("100000")) == Decimal("10000.00")

    def test_cupon_monto_fijo_no_supera_la_compra(self, empresa):
        cupon = Cupon.objects.create(
            empresa=empresa, codigo="FIJO50000", tipo_descuento=Cupon.TIPO_MONTO_FIJO, valor=Decimal("50000"),
            vigencia_desde=datetime.date.today(), vigencia_hasta=datetime.date.today() + datetime.timedelta(days=30),
        )
        assert cupon.calcular_descuento(Decimal("30000")) == Decimal("30000")

    def test_cupon_fuera_de_vigencia_es_invalido(self, empresa):
        cupon = Cupon.objects.create(
            empresa=empresa, codigo="VENCIDO", tipo_descuento=Cupon.TIPO_PORCENTAJE, valor=Decimal("10"),
            vigencia_desde=datetime.date.today() - datetime.timedelta(days=60),
            vigencia_hasta=datetime.date.today() - datetime.timedelta(days=30),
        )
        valido, motivo = cupon.es_valido(datetime.date.today(), Decimal("100000"))
        assert valido is False

    def test_cupon_con_usos_agotados_es_invalido(self, empresa):
        cupon = Cupon.objects.create(
            empresa=empresa, codigo="LIMITADO", tipo_descuento=Cupon.TIPO_PORCENTAJE, valor=Decimal("10"),
            vigencia_desde=datetime.date.today(), vigencia_hasta=datetime.date.today() + datetime.timedelta(days=30),
            usos_maximos=1, usos_actuales=1,
        )
        valido, _ = cupon.es_valido(datetime.date.today(), Decimal("100000"))
        assert valido is False

    def test_cupon_bajo_el_monto_minimo_es_invalido(self, empresa):
        cupon = Cupon.objects.create(
            empresa=empresa, codigo="MIN100K", tipo_descuento=Cupon.TIPO_PORCENTAJE, valor=Decimal("10"),
            vigencia_desde=datetime.date.today(), vigencia_hasta=datetime.date.today() + datetime.timedelta(days=30),
            monto_minimo_compra=Decimal("100000"),
        )
        valido, _ = cupon.es_valido(datetime.date.today(), Decimal("50000"))
        assert valido is False


@pytest.mark.django_db
class TestListaPrecio:
    def test_solo_una_lista_puede_ser_default_por_empresa(self, empresa, pyg, lista_precio):
        with pytest.raises(Exception):
            otra = ListaPrecio(empresa=empresa, nombre="Otra Lista", moneda=pyg, es_default=True)
            otra.full_clean()

    def test_precio_de_producto_en_lista(self, lista_precio, producto):
        PrecioProducto.objects.create(lista_precio=lista_precio, producto=producto, precio=Decimal("95000"))
        precio = lista_precio.precios.get(producto=producto)
        assert precio.precio == Decimal("95000")


@pytest.mark.django_db
class TestPromocion:
    def test_promocion_vigente_aplica_dentro_del_rango_de_fechas(self, empresa):
        promo = Promocion.objects.create(
            empresa=empresa, nombre="Oferta", descuento_porcentaje=Decimal("15"),
            vigencia_desde=datetime.date.today() - datetime.timedelta(days=1),
            vigencia_hasta=datetime.date.today() + datetime.timedelta(days=1),
        )
        assert promo.vigente(datetime.date.today()) is True
        assert promo.vigente(datetime.date.today() + datetime.timedelta(days=10)) is False

    def test_promocion_aplica_a_producto_especifico(self, empresa, producto):
        promo = Promocion.objects.create(
            empresa=empresa, nombre="Oferta Mouse", descuento_porcentaje=Decimal("15"),
            vigencia_desde=datetime.date.today(), vigencia_hasta=datetime.date.today() + datetime.timedelta(days=1),
        )
        promo.productos.add(producto)
        assert promo.aplica_a(producto) is True
