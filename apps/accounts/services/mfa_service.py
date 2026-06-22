"""
Servicio de MFA (TOTP) - Módulo 1.

El secreto TOTP nunca se persiste en texto plano: se cifra con Fernet
usando una clave derivada de SECRET_KEY antes de guardarlo en
`User.mfa_secret_encrypted`.
"""
import base64
import hashlib
import secrets
import string

import pyotp
from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from ..models import MFABackupCode


def _get_fernet() -> Fernet:
    # Deriva una clave Fernet válida (32 bytes urlsafe-base64) a partir de
    # SECRET_KEY, para no requerir una variable de entorno adicional.
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


class MFAService:
    BACKUP_CODES_COUNT = 8

    @staticmethod
    def generate_secret() -> str:
        return pyotp.random_base32()

    @staticmethod
    def encrypt_secret(raw_secret: str) -> str:
        return _get_fernet().encrypt(raw_secret.encode()).decode()

    @staticmethod
    def decrypt_secret(encrypted_secret: str) -> str:
        return _get_fernet().decrypt(encrypted_secret.encode()).decode()

    @classmethod
    def start_enrollment(cls, user) -> dict:
        """Genera un nuevo secreto (aún no activado) y la URI para el QR."""
        raw_secret = cls.generate_secret()
        user.mfa_secret_encrypted = cls.encrypt_secret(raw_secret)
        user.mfa_enabled = False
        user.save(update_fields=["mfa_secret_encrypted", "mfa_enabled"])

        totp = pyotp.TOTP(raw_secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email, issuer_name="ERP Stock"
        )
        return {"secret": raw_secret, "provisioning_uri": provisioning_uri}

    @classmethod
    def confirm_enrollment(cls, user, otp_code: str):
        """
        Verifica el primer código ingresado por el usuario y activa MFA.
        Devuelve None si el código es incorrecto, o la lista de códigos de
        respaldo en texto plano si se activó correctamente (solo se
        muestran una vez; luego solo existen hasheados en la base).
        """
        if not cls.verify_code(user, otp_code):
            return None
        user.mfa_enabled = True
        user.save(update_fields=["mfa_enabled"])
        return cls._generate_backup_codes(user)

    @classmethod
    def verify_code(cls, user, otp_code: str) -> bool:
        if not user.mfa_secret_encrypted:
            return False
        raw_secret = cls.decrypt_secret(user.mfa_secret_encrypted)
        totp = pyotp.TOTP(raw_secret)
        return totp.verify(otp_code, valid_window=1)

    @classmethod
    def disable(cls, user):
        user.mfa_enabled = False
        user.mfa_secret_encrypted = ""
        user.save(update_fields=["mfa_enabled", "mfa_secret_encrypted"])
        user.mfa_backup_codes.all().delete()

    @classmethod
    def _generate_backup_codes(cls, user) -> list:
        user.mfa_backup_codes.all().delete()
        plain_codes = []
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(cls.BACKUP_CODES_COUNT):
            code = "".join(secrets.choice(alphabet) for _ in range(10))
            plain_codes.append(code)
            MFABackupCode.objects.create(user=user, code_hash=make_password(code))
        return plain_codes

    @classmethod
    def verify_backup_code(cls, user, code: str) -> bool:
        for backup in user.mfa_backup_codes.filter(used_at__isnull=True):
            if check_password(code, backup.code_hash):
                backup.used_at = timezone.now()
                backup.save(update_fields=["used_at"])
                return True
        return False
