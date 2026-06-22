"""
Conftest raíz de pytest: fixtures compartidos por toda la suite.

Las variables de entorno necesarias para que Django cargue settings
(SECRET_KEY, etc.) se definen en `config/settings/test.py`, no acá —
ese módulo se importa más temprano en el ciclo de arranque de
pytest-django que este conftest, así que poner los defaults ahí es lo
que realmente garantiza el orden correcto.
"""
import datetime
from decimal import Decimal

import pytest


@pytest.fixture
def pyg(db):
    from apps.currencies.models import Currency

    return Currency.objects.create(code="PYG", name="Guaraní", symbol="₲", decimal_places=0, is_base=True)


@pytest.fixture
def usd(db, pyg):
    from apps.currencies.models import Currency, ExchangeRate

    moneda = Currency.objects.create(code="USD", name="Dólar", symbol="$", decimal_places=2)
    ExchangeRate.objects.create(currency=moneda, rate_to_base=Decimal("7500"), effective_date=datetime.date.today())
    return moneda


@pytest.fixture
def empresa(db, pyg):
    from apps.companies.models import Empresa

    return Empresa.objects.create(
        razon_social="Netlogic SRL", nombre_comercial="Netlogic", ruc="80012345-6", moneda_default=pyg,
        direccion="Av. Mcal. López 1234", timbrado_numero="12345678",
    )


@pytest.fixture
def sucursal(db, empresa):
    from apps.companies.models import Sucursal

    return Sucursal.objects.create(empresa=empresa, codigo="001", nombre="Casa Matriz", es_casa_matriz=True)


@pytest.fixture
def deposito(db, sucursal):
    from apps.companies.models import Deposito

    return Deposito.objects.create(sucursal=sucursal, codigo="D01", nombre="Depósito Central", permite_venta_directa=True)


@pytest.fixture
def deposito_b(db, sucursal):
    from apps.companies.models import Deposito

    return Deposito.objects.create(sucursal=sucursal, codigo="D02", nombre="Depósito Secundario", permite_venta_directa=True)


@pytest.fixture
def punto_venta(db, sucursal):
    from apps.companies.models import PuntoVenta

    return PuntoVenta.objects.create(
        sucursal=sucursal, codigo="P01", nombre="Caja 1", establecimiento="001", punto_expedicion="001"
    )


@pytest.fixture
def user(db, empresa):
    from apps.accounts.models import User

    return User.objects.create_user(
        email="jorge@netlogic.com.py", password="Clave123!", first_name="Jorge", last_name="Test",
        empresa=empresa, is_staff=True,
    )


@pytest.fixture
def unidad_medida(db):
    from apps.products.models import UnidadMedida

    return UnidadMedida.objects.create(codigo="UN", nombre="Unidad")


@pytest.fixture
def impuesto_iva10(db):
    from apps.products.models import Impuesto

    return Impuesto.objects.create(nombre="IVA 10%", tasa_porcentaje=Decimal("10"))


@pytest.fixture
def producto(db, empresa, pyg, unidad_medida):
    from apps.products.models import Producto

    return Producto.objects.create(
        empresa=empresa, tipo=Producto.TIPO_PRODUCTO, codigo="P-001", nombre="Mouse Inalámbrico",
        unidad_medida=unidad_medida, moneda_costo=pyg, moneda_precio=pyg,
        precio=Decimal("100000"), costo=Decimal("60000"),
        stock_minimo=Decimal("10"), stock_maximo=Decimal("100"),
    )


@pytest.fixture
def cliente(db, empresa, pyg):
    from apps.customers.models import Cliente

    return Cliente.objects.create(empresa=empresa, razon_social="Comercial ABC SA", ruc="80077777-3", moneda_default=pyg)


@pytest.fixture
def proveedor(db, empresa, pyg):
    from apps.suppliers.models import Proveedor

    return Proveedor.objects.create(empresa=empresa, razon_social="Tecno Import SA", ruc="80099999-1", moneda_default=pyg)


@pytest.fixture
def lista_precio(db, empresa, pyg):
    from apps.pricing.models import ListaPrecio

    return ListaPrecio.objects.create(empresa=empresa, nombre="Lista General", moneda=pyg, es_default=True)


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    from rest_framework_simplejwt.tokens import RefreshToken

    token = RefreshToken.for_user(user).access_token
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client
