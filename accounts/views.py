from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json

from .forms import LoginForm
from .models import User
from .policies import roles_required


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
    if not request.user.is_active or request.user.role != role:
        raise PermissionDenied
    from .dashboard import dashboard_context
    return render(request, f'accounts/{role}_home.html', dashboard_context(request.user, request))


@roles_required(User.Role.ADMINISTRATOR)
def setup(request):
    from .dashboard import dashboard_context
    return render(request, 'accounts/setup.html', dashboard_context(request.user))


@roles_required(*User.Role.values)
@require_POST
def save_layout(request):
    from .layouts import allowed_widgets
    from .models import WorkspaceLayout
    if len(request.body) > 4096:
        return JsonResponse({'error': 'Layout preferences are too large.'}, status=400)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != {'page', 'hidden', 'collapsed'}:
            raise ValueError
        if not isinstance(data['page'], str):
            raise ValueError
        allowed = allowed_widgets(request.user, data['page'])
        if allowed is None:
            raise PermissionDenied
        for name in ('hidden', 'collapsed'):
            values = data[name]
            if not isinstance(values, list) or len(values) > len(allowed) or any(not isinstance(v, str) or v not in allowed for v in values):
                raise ValueError
        preferences = {name: sorted(set(data[name])) for name in ('hidden', 'collapsed')}
    except (ValueError, TypeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Choose valid layout sections.'}, status=400)
    WorkspaceLayout.objects.update_or_create(user=request.user, page=data['page'], defaults={'preferences': preferences})
    return JsonResponse({'saved': True})
