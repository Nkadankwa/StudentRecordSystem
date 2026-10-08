from .models import User


class AdministratorAdminMixin:
    """Model admin is for administrators; teachers use scoped application forms."""
    def allowed(self, request):
        return request.user.is_active and request.user.role == User.Role.ADMINISTRATOR

    def has_module_permission(self, request):
        return self.allowed(request) and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return self.allowed(request) and super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return self.allowed(request) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.allowed(request) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self.allowed(request) and super().has_delete_permission(request, obj)
