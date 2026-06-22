from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.billing.models import DocumentoVenta
from apps.inventory.services import InventoryService
from apps.orders.models import PedidoWeb
from apps.orders.serializers import PedidoWebSerializer
from apps.orders.services import OrderError, OrderService
from apps.products.models import Producto

from .auth import PortalJWTAuthentication
from .models import PortalUser
from .serializers import (
    PortalChangePasswordInputSerializer,
    PortalCrearPedidoInputSerializer,
    PortalLoginInputSerializer,
    PortalUserCreateInputSerializer,
    PortalUserSerializer,
)


def _portal_tokens_for(portal_user: PortalUser) -> dict:
    refresh = RefreshToken()
    refresh["portal_user_id"] = portal_user.id
    access = refresh.access_token
    access["portal_user_id"] = portal_user.id
    return {"refresh": str(refresh), "access": str(access)}


class PortalLoginView(APIView):
    """POST /api/customer-portal/auth/login/ -- login del portal (independiente del login interno)."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PortalLoginInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        portal_user = PortalUser.objects.filter(email=data["email"].strip().lower()).first()
        if portal_user is None or not portal_user.check_password(data["password"]):
            return Response({"detail": "Email o contraseña incorrectos."}, status=status.HTTP_400_BAD_REQUEST)
        if not portal_user.is_active:
            return Response({"detail": "Esta cuenta de portal está inactiva."}, status=status.HTTP_400_BAD_REQUEST)

        from django.utils import timezone

        portal_user.last_login_at = timezone.now()
        portal_user.save(update_fields=["last_login_at"])

        return Response(_portal_tokens_for(portal_user))


class PortalProvisionUserView(APIView):
    """
    POST /api/customer-portal/admin/provisionar-usuario/
    Usado por personal interno (NO por el cliente) para dar de alta una
    cuenta de portal. Usa la autenticación interna estándar (JWT de empleados).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.customers.models import Cliente

        serializer = PortalUserCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cliente = get_object_or_404(Cliente, pk=data["cliente_id"])
        if not request.user.is_superuser and cliente.empresa_id != request.user.empresa_id:
            return Response({"detail": "No tiene acceso a este cliente."}, status=status.HTTP_403_FORBIDDEN)

        portal_user = PortalUser(cliente=cliente, email=data["email"].strip().lower(), nombre=data["nombre"])
        portal_user.set_password(data["password"])
        portal_user.save()

        return Response(PortalUserSerializer(portal_user).data, status=status.HTTP_201_CREATED)


class PortalMeView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(PortalUserSerializer(request.user).data)


class PortalChangePasswordView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PortalChangePasswordInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not request.user.check_password(data["password_actual"]):
            return Response({"detail": "La contraseña actual es incorrecta."}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(data["password_nueva"])
        request.user.save(update_fields=["password_hash"])
        return Response({"detail": "Contraseña actualizada correctamente."})


class PortalStockDisponibleView(APIView):
    """GET /api/customer-portal/stock-disponible/?producto=<id> -- consulta de stock para el cliente del portal."""

    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        empresa = request.user.cliente.empresa
        productos_qs = Producto.objects.filter(empresa=empresa, active=True)

        producto_id = request.query_params.get("producto")
        if producto_id:
            productos_qs = productos_qs.filter(pk=producto_id)

        from apps.companies.models import Deposito

        depositos_venta = Deposito.objects.filter(sucursal__empresa=empresa, permite_venta_directa=True, active=True)

        data = []
        for producto in productos_qs[:200]:
            disponible = sum(
                InventoryService.cantidad_disponible_venta(producto, dep) for dep in depositos_venta
            )
            data.append({
                "producto_id": producto.id,
                "codigo": producto.codigo,
                "nombre": producto.nombre,
                "cantidad_disponible": disponible,
                "precio": producto.precio,
                "moneda": producto.moneda_precio.code,
            })
        return Response(data)


class PortalPedidosListView(APIView):
    """GET /api/customer-portal/pedidos/ -- pedidos del cliente logueado en el portal."""

    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        pedidos = PedidoWeb.objects.filter(cliente=request.user.cliente).select_related(
            "lista_precio", "deposito_reserva", "documento_venta"
        ).prefetch_related("items", "historial_estados").order_by("-fecha_pedido")
        return Response(PedidoWebSerializer(pedidos, many=True).data)


class PortalPedidoDetailView(APIView):
    """GET /api/customer-portal/pedidos/<id>/ -- seguimiento de un pedido puntual."""

    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pedido_id):
        pedido = get_object_or_404(PedidoWeb, pk=pedido_id, cliente=request.user.cliente)
        return Response(PedidoWebSerializer(pedido).data)


class PortalCrearPedidoView(APIView):
    """POST /api/customer-portal/pedidos/crear/ -- el cliente solicita un nuevo pedido desde su carrito."""

    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.companies.models import Deposito, Sucursal
        from apps.pricing.models import ListaPrecio

        serializer = PortalCrearPedidoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cliente = request.user.cliente
        sucursal = get_object_or_404(Sucursal, pk=data["sucursal"], empresa=cliente.empresa)
        lista_precio = get_object_or_404(ListaPrecio, pk=data["lista_precio"], empresa=cliente.empresa)
        deposito_reserva = get_object_or_404(Deposito, pk=data["deposito_reserva"])

        try:
            pedido = OrderService.crear_pedido(
                empresa=cliente.empresa, sucursal=sucursal, cliente=cliente, lista_precio=lista_precio,
                deposito_reserva=deposito_reserva, items_data=data["items"], portal_user=request.user,
                cupon_code=data.get("cupon_code") or None, observaciones=data.get("observaciones", ""),
            )
        except OrderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PedidoWebSerializer(pedido).data, status=status.HTTP_201_CREATED)


class PortalCancelarPedidoView(APIView):
    """POST /api/customer-portal/pedidos/<id>/cancelar/ -- el cliente cancela su propio pedido (si aún no se facturó)."""

    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pedido_id):
        pedido = get_object_or_404(PedidoWeb, pk=pedido_id, cliente=request.user.cliente)
        motivo = request.data.get("motivo", "Cancelado por el cliente desde el portal")
        try:
            pedido = OrderService.cancelar_pedido(pedido, motivo, usuario=None)
        except OrderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PedidoWebSerializer(pedido).data)


class PortalDocumentosView(APIView):
    """GET /api/customer-portal/documentos/?tipo=FACTURA -- facturas/presupuestos descargables del cliente."""

    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = DocumentoVenta.objects.filter(cliente=request.user.cliente).select_related("moneda").order_by("-fecha_emision")
        tipo = request.query_params.get("tipo")
        if tipo:
            qs = qs.filter(tipo_documento=tipo)

        data = [
            {
                "id": doc.id,
                "tipo_documento": doc.tipo_documento,
                "numero": doc.numero,
                "fecha_emision": doc.fecha_emision,
                "moneda": doc.moneda.code,
                "total": doc.total,
                "estado": doc.estado,
                "saldo_pendiente": doc.saldo_pendiente,
            }
            for doc in qs[:200]
        ]
        return Response(data)


class PortalEstadoCuentaView(APIView):
    """GET /api/customer-portal/estado-cuenta/ -- saldo pendiente y facturas impagas del cliente."""

    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        facturas_pendientes = DocumentoVenta.objects.filter(
            cliente=request.user.cliente, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            estado=DocumentoVenta.ESTADO_EMITIDA, saldo_pendiente__gt=0,
        ).order_by("fecha_vencimiento")

        saldo_total = sum((f.saldo_pendiente for f in facturas_pendientes), Decimal("0"))

        return Response({
            "saldo_total_pendiente": saldo_total,
            "limite_credito": request.user.cliente.limite_credito,
            "facturas_pendientes": [
                {
                    "numero": f.numero, "fecha_emision": f.fecha_emision,
                    "fecha_vencimiento": f.fecha_vencimiento, "saldo_pendiente": f.saldo_pendiente,
                }
                for f in facturas_pendientes
            ],
        })
