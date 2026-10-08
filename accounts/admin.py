from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .admin_policies import AdministratorAdminMixin
from .models import StudentProfile, TeacherProfile, User


class AccountCreationForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ('username', 'role')


class AccountChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'


@admin.register(User)
class AccountAdmin(AdministratorAdminMixin, UserAdmin):
    add_form = AccountCreationForm
    form = AccountChangeForm
    fieldsets = UserAdmin.fieldsets + (('Account role', {'fields': ('role',)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('Account role', {'fields': ('role',)}),)
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    list_filter = UserAdmin.list_filter + ('role',)


@admin.register(StudentProfile)
class StudentProfileAdmin(AdministratorAdminMixin, admin.ModelAdmin):
    list_display = ('student_number', 'user', 'date_of_birth', 'nationality')
    search_fields = ('student_number', 'user__username', 'user__first_name', 'user__last_name')
    list_select_related = ('user',)


@admin.register(TeacherProfile)
class TeacherProfileAdmin(AdministratorAdminMixin, admin.ModelAdmin):
    list_display = ('employee_number', 'user')
    search_fields = ('employee_number', 'user__username', 'user__first_name', 'user__last_name')
    list_select_related = ('user',)
