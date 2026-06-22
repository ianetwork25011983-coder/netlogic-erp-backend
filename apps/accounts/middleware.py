"""
Middlewares - Módulo 1.

EmpresaSucursalContextMiddleware: resuelve `request.empresa` y
`request.sucursal` a partir del usuario autenticado, validando que la
sucursal solicitada (header `X-Sucursal-Id`) esté entre las autorizadas.
Esto es lo que permite que el resto del ERP filtre cualquier queryset por
`request.empresa` / `request.sucursal` sin repetir esa lógica en cada vista.
"""
from django.http import JsonResponse


class EmpresaSucursalContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.empresa = None
        request.sucursal = None

        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            request.empresa = user.empresa

            sucursal_id = request.headers.get("X-Sucursal-Id")
            if sucursal_id:
                if not user.is_superuser and not user.sucursales.filter(pk=sucursal_id).exists():
                    return JsonResponse(
                        {"detail": "No tiene acceso a la sucursal solicitada."}, status=403
                    )
                from apps.companies.models import Sucursal

                request.sucursal = Sucursal.objects.filter(pk=sucursal_id).first()
            else:
                request.sucursal = user.sucursal_actual

        return self.get_response(request)
