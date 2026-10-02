from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import F

from .models import StudentProfile, User


def roles_required(*roles):
    def decorate(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_active or request.user.role not in roles:
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapped
    return decorate


def visible_students(user):
    queryset = StudentProfile.objects.select_related('user')
    if not user.is_authenticated or not user.is_active:
        return queryset.none()
    if user.role == User.Role.ADMINISTRATOR:
        return queryset
    if user.role == User.Role.STUDENT:
        return queryset.filter(user=user)
    if user.role == User.Role.TEACHER:
        return queryset.filter(
            enrollments__course__teaching_assignments__teacher__user=user,
            enrollments__term=F('enrollments__course__teaching_assignments__term'),
            enrollments__status__in=['active', 'completed'],
        ).distinct()
    return queryset.none()
