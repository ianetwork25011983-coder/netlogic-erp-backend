"""
Servicio de auditoría - Módulo 1.

Cualquier app del ERP (no solo accounts) puede llamar a `AuditService.log(...)`
para registrar una acción. Pensado para usarse desde signals (post_save,
post_delete) de los modelos de negocio, y desde las vistas de login/logout.
"""
from ..models import AuditLog


class AuditService:
    @staticmethod
    def log(
        action,
        user=None,
        instance=None,
        changes=None,
        request=None,
        empresa=None,
        sucursal=None,
    ):
        ip_address = None
        user_agent = ""
        if request is not None:
            ip_address = AuditService._get_client_ip(request)
            user_agent = request.META.get("HTTP_USER_AGENT", "")[:255]
            empresa = empresa or getattr(request, "empresa", None)
            sucursal = sucursal or getattr(request, "sucursal", None)

        model_name = instance.__class__.__name__ if instance is not None else ""
        object_id = str(getattr(instance, "pk", "")) if instance is not None else ""
        object_repr = str(instance)[:255] if instance is not None else ""

        return AuditLog.objects.create(
            user=user,
            action=action,
            model_name=model_name,
            object_id=object_id,
            object_repr=object_repr,
            changes=changes or {},
            empresa=empresa,
            sucursal=sucursal,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    def _get_client_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
