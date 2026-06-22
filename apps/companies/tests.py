import pytest
from django.core.exceptions import ValidationError

from apps.companies.models import Deposito, PuntoVenta, Sucursal


@pytest.mark.django_db
class TestSucursal:
    def test_solo_una_sucursal_puede_ser_casa_matriz(self, empresa, sucursal):
        with pytest.raises(ValidationError):
            otra = Sucursal(empresa=empresa, codigo="002", nombre="Sucursal 2", es_casa_matriz=True)
            otra.full_clean()

    def test_codigo_unico_por_empresa(self, empresa, sucursal):
        with pytest.raises(Exception):
            Sucursal.objects.create(empresa=empresa, codigo="001", nombre="Duplicada")


@pytest.mark.django_db
class TestDeposito:
    def test_depositos_ilimitados_por_sucursal(self, sucursal):
        for i in range(5):
            Deposito.objects.create(sucursal=sucursal, codigo=f"D{i}", nombre=f"Depósito {i}")
        assert Deposito.objects.filter(sucursal=sucursal).count() == 5


@pytest.mark.django_db
class TestPuntoVenta:
    def test_punto_venta_requiere_establecimiento_y_punto_expedicion(self, sucursal):
        pv = PuntoVenta.objects.create(
            sucursal=sucursal, codigo="P01", nombre="Caja 1", establecimiento="001", punto_expedicion="001"
        )
        assert pv.establecimiento == "001"
        assert pv.punto_expedicion == "001"
