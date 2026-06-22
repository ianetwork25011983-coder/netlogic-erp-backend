import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter  # noqa: E402

# A medida que se agreguen consumers (ej. notificaciones de stock en
# tiempo real, Módulo 13 - Dashboard), se registran acá dentro de un
# URLRouter para el protocolo "websocket".
application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
    }
)
