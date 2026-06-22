import pytest
from django.core.exceptions import ValidationError

from apps.products.models import Categoria, Lote, Producto, ProductoComponente, Serie


@pytest.mark.django_db
class TestProducto:
    def test_no_puede_controlar_lote_y_serie_a_la_vez(self, producto):
        producto.controla_lote = True
        producto.controla_serie = True
        with pytest.raises(ValidationError):
            producto.full_clean()

    def test_vencimiento_requiere_control_por_lote(self, producto):
        producto.controla_lote = False
        producto.controla_vencimiento = True
        with pytest.raises(ValidationError):
            producto.full_clean()

    def test_codigo_unico_por_empresa(self, empresa, producto):
        with pytest.raises(Exception):
            Producto.objects.create(
                empresa=empresa, tipo=Producto.TIPO_PRODUCTO, codigo="P-001", nombre="Otro",
                unidad_medida=producto.unidad_medida, moneda_costo=producto.moneda_costo, moneda_precio=producto.moneda_precio,
            )

    def test_servicio_no_descuenta_stock(self, empresa, unidad_medida, pyg):
        servicio = Producto.objects.create(
            empresa=empresa, tipo=Producto.TIPO_SERVICIO, codigo="S-001", nombre="Instalación",
            unidad_medida=unidad_medida, moneda_costo=pyg, moneda_precio=pyg,
        )
        assert servicio.descuenta_stock is False

    def test_combo_usa_componentes(self, empresa, unidad_medida, pyg, producto):
        combo = Producto.objects.create(
            empresa=empresa, tipo=Producto.TIPO_COMBO, codigo="C-001", nombre="Combo Oficina",
            unidad_medida=unidad_medida, moneda_costo=pyg, moneda_precio=pyg,
        )
        assert combo.usa_componentes is True
        ProductoComponente.objects.create(producto_padre=combo, producto_componente=producto, cantidad=2)
        assert combo.componentes.count() == 1


@pytest.mark.django_db
class TestProductoComponente:
    def test_un_producto_no_puede_ser_componente_de_si_mismo(self, producto):
        producto.tipo = Producto.TIPO_KIT
        producto.save()
        componente = ProductoComponente(producto_padre=producto, producto_componente=producto, cantidad=1)
        with pytest.raises(ValidationError):
            componente.full_clean()


@pytest.mark.django_db
class TestLote:
    def test_lote_requiere_que_el_producto_controle_por_lote(self, producto):
        producto.controla_lote = False
        producto.save()
        lote = Lote(producto=producto, numero_lote="L001")
        with pytest.raises(ValidationError):
            lote.full_clean()

    def test_lote_se_crea_si_el_producto_controla_lote(self, producto):
        producto.controla_lote = True
        producto.save()
        lote = Lote.objects.create(producto=producto, numero_lote="L001")
        assert lote.numero_lote == "L001"


@pytest.mark.django_db
class TestSerie:
    def test_serie_requiere_que_el_producto_controle_por_serie(self, producto):
        serie = Serie(producto=producto, numero_serie="SN001")
        with pytest.raises(ValidationError):
            serie.full_clean()


@pytest.mark.django_db
class TestCategoria:
    def test_categoria_puede_tener_subcategorias(self, empresa):
        padre = Categoria.objects.create(empresa=empresa, nombre="Electrónica")
        hija = Categoria.objects.create(empresa=empresa, nombre="Periféricos", parent=padre)
        assert hija.parent == padre
        assert str(hija) == "Electrónica > Periféricos"

    def test_categoria_no_puede_ser_su_propio_padre(self, empresa):
        categoria = Categoria.objects.create(empresa=empresa, nombre="Electrónica")
        categoria.parent = categoria
        with pytest.raises(ValidationError):
            categoria.full_clean()
