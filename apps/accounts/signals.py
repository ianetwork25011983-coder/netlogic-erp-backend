from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.utils import timezone

from .models import AuditLog, LoginHistory
from .services.audit_service import AuditService


@receiver(user_logged_in)
def on_login_success(sender, request, user, **kwargs):
    user.failed_login_attempts = 0
    user.locked_until = None
    user.save(update_fields=["failed_login_attempts", "locked_until"])

    LoginHistory.objects.create(
        user=user,
        email_attempted=user.email,
        ip_address=AuditService._get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255] if request else "",
        success=True,
        mfa_used=user.mfa_enabled,
    )
    AuditService.log(AuditLog.ACTION_LOGIN, user=user, request=request)


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user is not None:
        AuditService.log(AuditLog.ACTION_LOGOUT, user=user, request=request)


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    from django.conf import settings

    from .models import User

    email = credentials.get("email", credentials.get("username", ""))
    LoginHistory.objects.create(
        user=None,
        email_attempted=email,
        ip_address=AuditService._get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255] if request else "",
        success=False,
        failure_reason="Credenciales inválidas",
    )

    user = User.objects.filter(email=email).first()
    if user:
        user.failed_login_attempts += 1
        max_attempts = getattr(settings, "MAX_LOGIN_ATTEMPTS", 5)
        lock_minutes = getattr(settings, "LOGIN_LOCKOUT_MINUTES", 15)
        if user.failed_login_attempts >= max_attempts:
            user.locked_until = timezone.now() + timezone.timedelta(minutes=lock_minutes)
        user.save(update_fields=["failed_login_attempts", "locked_until"])
        AuditService.log(AuditLog.ACTION_LOGIN_FAILED, user=user, request=request)
