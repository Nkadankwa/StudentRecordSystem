from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import LoginForm
from .models import User


ROLE_ROUTES = {
    User.Role.STUDENT: 'accounts:student_home',
    User.Role.TEACHER: 'accounts:teacher_home',
    User.Role.ADMINISTRATOR: 'accounts:administrator_home',
}


def role_route(user):
    try:
        return ROLE_ROUTES[user.role]
    except KeyError:
        raise PermissionDenied


class AccountLoginView(LoginView):
    authentication_form = LoginForm
    template_name = 'accounts/login.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'You are signed in.')
        return response

    def get_default_redirect_url(self):
        return reverse(role_route(self.request.user))


class AccountLogoutView(LogoutView):
    next_page = 'accounts:login'
    redirect_field_name = None


@login_required
def home(request):
    return redirect(role_route(request.user))


@login_required
def role_home(request, role):
    if request.user.role != role:
        raise PermissionDenied
    return render(request, f'accounts/{role}_home.html')
