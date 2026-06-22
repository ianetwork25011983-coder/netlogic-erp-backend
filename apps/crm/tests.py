from decimal import Decimal

import pytest

from apps.crm.models import Contacto, EtapaPipeline, Oportunidad, Prospecto
from apps.crm.services import CRMError, CRMService


@pytest.mark.django_db
class TestConvertirProspecto:
    def test_convertir_prospecto_crea_cliente_y_migra_contactos(self, empresa, pyg):
        prospecto = Prospecto.objects.create(empresa=empresa, razon_social="Comercial ABC SA", contacto_nombre="Ana Pérez", email="ana@abc.com")
        Contacto.objects.create(prospecto=prospecto, nombre="Ana Pérez", cargo="Compras", es_principal=True)

        cliente = CRMService.convertir_prospecto_a_cliente(prospecto, ruc="80077777-3", moneda_default=pyg, tipo_contribuyente="JURIDICA")

        prospecto.refresh_from_db()
        assert prospecto.estado == Prospecto.ESTADO_CONVERTIDO
        assert prospecto.cliente_convertido == cliente
        assert cliente.contactos.count() == 1
        assert cliente.contactos.first().nombre == "Ana Pérez"

    def test_no_se_puede_convertir_dos_veces(self, empresa, pyg):
        prospecto = Prospecto.objects.create(empresa=empresa, razon_social="Comercial ABC SA")
        CRMService.convertir_prospecto_a_cliente(prospecto, ruc="80077777-3", moneda_default=pyg)
        with pytest.raises(CRMError):
            CRMService.convertir_prospecto_a_cliente(prospecto, ruc="80077777-3", moneda_default=pyg)


@pytest.mark.django_db
class TestPipeline:
    def test_mover_a_etapa_ganada_actualiza_estado(self, empresa, cliente, pyg):
        etapa_inicial = EtapaPipeline.objects.create(empresa=empresa, nombre="Nuevo", orden=1)
        etapa_ganada = EtapaPipeline.objects.create(empresa=empresa, nombre="Ganado", orden=2, es_ganada=True)
        oportunidad = Oportunidad.objects.create(
            empresa=empresa, cliente=cliente, nombre="Venta X", etapa_pipeline=etapa_inicial,
            valor_estimado=Decimal("1000000"), moneda=pyg,
        )
        CRMService.mover_oportunidad_etapa(oportunidad, etapa_ganada)
        oportunidad.refresh_from_db()
        assert oportunidad.estado == Oportunidad.ESTADO_GANADA

    def test_mover_a_etapa_perdida_guarda_motivo(self, empresa, cliente, pyg):
        etapa_inicial = EtapaPipeline.objects.create(empresa=empresa, nombre="Nuevo", orden=1)
        etapa_perdida = EtapaPipeline.objects.create(empresa=empresa, nombre="Perdido", orden=2, es_perdida=True)
        oportunidad = Oportunidad.objects.create(
            empresa=empresa, cliente=cliente, nombre="Venta X", etapa_pipeline=etapa_inicial,
            valor_estimado=Decimal("1000000"), moneda=pyg,
        )
        CRMService.mover_oportunidad_etapa(oportunidad, etapa_perdida, motivo_perdida="Precio muy alto")
        oportunidad.refresh_from_db()
        assert oportunidad.estado == Oportunidad.ESTADO_PERDIDA
        assert oportunidad.motivo_perdida == "Precio muy alto"

    def test_pipeline_resumen_solo_cuenta_abiertas(self, empresa, cliente, pyg):
        etapa = EtapaPipeline.objects.create(empresa=empresa, nombre="Nuevo", orden=1)
        Oportunidad.objects.create(empresa=empresa, cliente=cliente, nombre="A", etapa_pipeline=etapa, valor_estimado=Decimal("500000"), moneda=pyg)
        Oportunidad.objects.create(empresa=empresa, cliente=cliente, nombre="B", etapa_pipeline=etapa, valor_estimado=Decimal("300000"), moneda=pyg)

        resumen = CRMService.pipeline_resumen(empresa)
        etapa_resumen = next(r for r in resumen if r["etapa"] == "Nuevo")
        assert etapa_resumen["cantidad"] == 2
        assert etapa_resumen["valor_total"] == Decimal("800000")


@pytest.mark.django_db
class TestOportunidadValidacion:
    def test_oportunidad_no_puede_tener_cliente_y_prospecto_a_la_vez(self, empresa, cliente, pyg):
        prospecto = Prospecto.objects.create(empresa=empresa, razon_social="Otro")
        etapa = EtapaPipeline.objects.create(empresa=empresa, nombre="Nuevo", orden=1)
        oportunidad = Oportunidad(
            empresa=empresa, cliente=cliente, prospecto=prospecto, nombre="Inválida",
            etapa_pipeline=etapa, valor_estimado=Decimal("1"), moneda=pyg,
        )
        with pytest.raises(Exception):
            oportunidad.full_clean()
