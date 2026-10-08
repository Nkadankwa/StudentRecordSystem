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


def visible_assignments(user):
    from academics.models import TeachingAssignment
    qs = TeachingAssignment.objects.select_related('course', 'term__academic_year', 'teacher__user')
    if not user.is_authenticated or not user.is_active:
        return qs.none()
    if user.role == User.Role.ADMINISTRATOR:
        return qs
    if user.role == User.Role.TEACHER:
        return qs.filter(teacher__user=user)
    return qs.none()


def scoped_academic(qs, user, course_field, term_field):
    from django.db.models import Exists, OuterRef
    assignments = visible_assignments(user).filter(course_id=OuterRef(course_field), term_id=OuterRef(term_field))
    if not user.is_authenticated or not user.is_active:
        return qs.none()
    if user.role == User.Role.ADMINISTRATOR:
        return qs
    if user.role == User.Role.TEACHER:
        return qs.filter(Exists(assignments))
    return qs.none()


def visible_assessments(user):
    from academics.models import Assessment
    return scoped_academic(Assessment.objects.select_related('course', 'term__academic_year'), user, 'course_id', 'term_id')


def visible_scores(user):
    from academics.models import Score
    qs = Score.objects.select_related('student__user', 'assessment__course', 'assessment__term__academic_year', 'updated_by')
    if user.is_authenticated and user.is_active and user.role == User.Role.STUDENT:
        return qs.filter(student__user=user)
    return scoped_academic(qs, user, 'assessment__course_id', 'assessment__term_id')


def visible_attendance(user):
    from academics.models import AttendanceRecord
    qs = AttendanceRecord.objects.select_related('student__user', 'session__course', 'session__term__academic_year', 'updated_by')
    if user.is_authenticated and user.is_active and user.role == User.Role.STUDENT:
        return qs.filter(student__user=user)
    return scoped_academic(qs, user, 'session__course_id', 'session__term_id')


def visible_enrollments(user):
    from academics.models import Enrollment
    qs = Enrollment.objects.select_related('student__user', 'course', 'term__academic_year')
    if user.is_authenticated and user.is_active and user.role == User.Role.STUDENT:
        return qs.filter(student__user=user)
    return scoped_academic(qs, user, 'course_id', 'term_id')
