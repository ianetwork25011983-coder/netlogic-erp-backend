import pytest

from apps.customers.models import Cliente


@pytest.mark.django_db
class TestCliente:
    def test_ruc_unico_por_empresa(self, empresa, cliente):
        with pytest.raises(Exception):
            Cliente.objects.create(
                empresa=empresa, razon_social="Otro Cliente", ruc=cliente.ruc, moneda_default=cliente.moneda_default,
            )

    def test_es_vip_default_false(self, cliente):
        assert cliente.es_vip is False
