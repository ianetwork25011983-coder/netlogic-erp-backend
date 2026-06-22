"""
Permisos custom de DRF para el aislamiento multiempresa/multisucursal.

Estos permisos asumen que `EmpresaSucursalContextMiddleware` ya resolvió
`request.empresa` y `request.sucursal` antes de llegar a la vista.
"""
from rest_framework.permissions import BasePermission


class IsSameEmpresa(BasePermission):
    """El objeto consultado debe pertenecer a la empresa activa del usuario."""

    message = "No tiene acceso a datos de otra empresa."

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        obj_empresa = getattr(obj, "empresa", None) or getattr(obj, "empresa_id", None)
        return obj_empresa == request.empresa


class IsSameSucursal(BasePermission):
    """El objeto consultado debe pertenecer a una sucursal autorizada para el usuario."""

    message = "No tiene acceso a datos de esta sucursal."

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        sucursal = getattr(obj, "sucursal", None)
        if sucursal is None:
            return True
        return request.user.has_access_to_sucursal(sucursal)


class HasRolePermission(BasePermission):
    """
    Verifica que el usuario tenga, dentro de alguno de sus RoleAssignment
    activos y vigentes (con alcance en la empresa/sucursal actual o global),
    el permiso Django requerido por la vista (`required_permission` en la view).
    """

    message = "No cuenta con el permiso requerido para esta acción."

    def has_permission(self, request, view):
        required = getattr(view, "required_permission", None)
        if required is None:
            return True
        if request.user.is_superuser:
            return True
        return request.user.has_perm(required)
