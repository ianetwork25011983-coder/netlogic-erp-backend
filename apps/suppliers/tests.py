import pytest

from apps.suppliers.models import Proveedor


@pytest.mark.django_db
class TestProveedor:
    def test_ruc_unico_por_empresa(self, empresa, proveedor):
        with pytest.raises(Exception):
            Proveedor.objects.create(
                empresa=empresa, razon_social="Otro Proveedor", ruc=proveedor.ruc, moneda_default=proveedor.moneda_default,
            )

    def test_str_usa_nombre_comercial_si_existe(self, empresa, pyg):
        prov = Proveedor.objects.create(
            empresa=empresa, razon_social="Razón Social SA", nombre_comercial="Nombre Corto",
            ruc="80011111-1", moneda_default=pyg,
        )
        assert str(prov) == "Nombre Corto"
