from rest_framework.routers import DefaultRouter

from django.urls import path

from . import views

router = DefaultRouter()
router.register("users", views.UserViewSet, basename="user")
router.register("roles", views.RoleViewSet, basename="role")
router.register("role-assignments", views.RoleAssignmentViewSet, basename="roleassignment")

urlpatterns = [
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/mfa/verify/", views.MFAVerifyView.as_view(), name="auth-mfa-verify"),
    path("auth/mfa/enroll/", views.MFAEnrollView.as_view(), name="auth-mfa-enroll"),
    path("auth/mfa/enroll/confirm/", views.MFAEnrollConfirmView.as_view(), name="auth-mfa-enroll-confirm"),
    path("auth/mfa/disable/", views.MFADisableView.as_view(), name="auth-mfa-disable"),
    path("auth/me/", views.MeView.as_view(), name="auth-me"),
    path("auth/login-history/", views.LoginHistoryListView.as_view(), name="auth-login-history"),
] + router.urls
