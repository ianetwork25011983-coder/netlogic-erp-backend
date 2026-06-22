"""
Servicio de CRM (Módulo 6).
"""
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import EtapaPipeline, Oportunidad, Prospecto


class CRMError(Exception):
    pass


class CRMService:
    @staticmethod
    @transaction.atomic
    def convertir_prospecto_a_cliente(
        prospecto, *, ruc, moneda_default, tipo_contribuyente="FISICA", dias_credito=0, limite_credito=0,
    ):
        from apps.customers.models import Cliente

        if prospecto.estado == Prospecto.ESTADO_CONVERTIDO:
            raise CRMError("Este prospecto ya fue convertido a cliente.")

        cliente = Cliente.objects.create(
            empresa=prospecto.empresa,
            razon_social=prospecto.razon_social,
            nombre_comercial=prospecto.nombre_comercial,
            ruc=ruc,
            tipo_contribuyente=tipo_contribuyente,
            contacto_nombre=prospecto.contacto_nombre,
            telefono=prospecto.telefono,
            email=prospecto.email,
            moneda_default=moneda_default,
            dias_credito=dias_credito,
            limite_credito=limite_credito,
        )

        prospecto.estado = Prospecto.ESTADO_CONVERTIDO
        prospecto.cliente_convertido = cliente
        prospecto.fecha_conversion = timezone.now()
        prospecto.save(update_fields=["estado", "cliente_convertido", "fecha_conversion"])

        # Los contactos del prospecto pasan a ser contactos del nuevo cliente.
        prospecto.contactos.update(cliente=cliente, prospecto=None)

        return cliente

    @staticmethod
    def mover_oportunidad_etapa(oportunidad, nueva_etapa: EtapaPipeline, motivo_perdida=""):
        oportunidad.etapa_pipeline = nueva_etapa
        if nueva_etapa.es_ganada:
            oportunidad.estado = Oportunidad.ESTADO_GANADA
        elif nueva_etapa.es_perdida:
            oportunidad.estado = Oportunidad.ESTADO_PERDIDA
            oportunidad.motivo_perdida = motivo_perdida
        oportunidad.save(update_fields=["etapa_pipeline", "estado", "motivo_perdida", "updated_at"])
        return oportunidad

    @staticmethod
    def pipeline_resumen(empresa):
        """Cantidad y valor estimado de oportunidades abiertas, agrupado por etapa."""
        abiertas = Q(oportunidades__estado=Oportunidad.ESTADO_ABIERTA)
        etapas = (
            EtapaPipeline.objects.filter(empresa=empresa, active=True)
            .order_by("orden")
            .annotate(
                cantidad_oportunidades=Count("oportunidades", filter=abiertas),
                valor_total=Sum("oportunidades__valor_estimado", filter=abiertas),
            )
        )
        return [
            {
                "etapa": etapa.nombre,
                "orden": etapa.orden,
                "cantidad": etapa.cantidad_oportunidades or 0,
                "valor_total": etapa.valor_total or 0,
            }
            for etapa in etapas
        ]
