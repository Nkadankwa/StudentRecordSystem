"""Dashboard records share the application's authorization policies."""
from django import forms
from django.core.paginator import Paginator
from django.db.models import Count, OuterRef, Subquery, IntegerField, FloatField, Avg, F, Q, Prefetch, ExpressionWrapper, Case, When
from django.db.models.functions import Cast
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone
from academics.models import Course, Enrollment, Term
from .models import User
from .policies import (visible_students, visible_assignments, visible_assessments,
                       visible_scores, visible_attendance, visible_enrollments)


def assignment_queryset(user):
    roster = Enrollment.objects.filter(course_id=OuterRef('course_id'), term_id=OuterRef('term_id')).exclude(
        status='withdrawn').order_by().values('course_id').annotate(total=Count('student_id')).values('total')
    return visible_assignments(user).annotate(roster_count=Coalesce(Subquery(roster, output_field=IntegerField()), 0))


class DirectoryFilter(forms.Form):
    q = forms.CharField(required=False, max_length=100, label='Student name or number')
    term = forms.ModelChoiceField(queryset=Term.objects.select_related('academic_year'), required=False, empty_label='All terms')


def administrator_directory(user, params):
    form = DirectoryFilter(params)
    students = visible_students(user)
    enrollments = visible_enrollments(user).exclude(status='withdrawn')
    scores, attendance = visible_scores(user), visible_attendance(user)
    assignments = visible_assignments(user)
    assessments = visible_assessments(user)
    if form.is_valid():
        term = form.cleaned_data['term']
        if term:
            enrollments = enrollments.filter(term=term)
            students = students.filter(enrollments__in=enrollments).distinct()
            scores = scores.filter(assessment__term=term)
            attendance = attendance.filter(session__term=term)
            assignments = assignments.filter(term=term)
            assessments = assessments.filter(term=term)
        query = form.cleaned_data['q']
        if query:
            students = students.filter(Q(student_number__istartswith=query) | Q(user__first_name__istartswith=query) | Q(user__last_name__istartswith=query))
    else:
        students = students.none()
    maximum = Case(When(resit_value__isnull=False, then=Cast(KeyTextTransform('maximum_score', 'resit_policy_snapshot'), FloatField())),
                   default=F('assessment__maximum_score'), output_field=FloatField())
    score_mean = scores.filter(student_id=OuterRef('pk')).order_by().values('student_id').annotate(
        mean=Avg(ExpressionWrapper(100.0 * Coalesce(F('resit_effective_value'), F('value')) / maximum, output_field=FloatField()))).values('mean')
    attendance_rate = attendance.filter(student_id=OuterRef('pk')).order_by().values('student_id').annotate(
        rate=100.0 * Count('pk', filter=Q(status='present')) / Count('pk')).values('rate')
    students = students.annotate(score_mean=Subquery(score_mean, output_field=FloatField()), present_rate=Subquery(attendance_rate, output_field=FloatField())).prefetch_related(
        Prefetch('enrollments', queryset=enrollments.select_related('course', 'term').order_by('course__code'), to_attr='directory_courses')).order_by('student_number')
    page_size = params.get('size', '5')
    page_size = int(page_size) if page_size in {'5', '10', '25'} else 5
    page = Paginator(students, page_size).get_page(params.get('page'))
    preserved = params.copy()
    preserved.pop('page', None)
    attendance_totals = attendance.aggregate(total=Count('pk'), present=Count('pk', filter=Q(status='present')),
        late=Count('pk', filter=Q(status='late')), absent=Count('pk', filter=Q(status='absent')), excused=Count('pk', filter=Q(status='excused')))
    attendance_totals['rate'] = (100 * attendance_totals['present'] / attendance_totals['total']) if attendance_totals['total'] else None
    return {'directory_form': form, 'directory_page': page, 'directory_query': preserved.urlencode(),
        'directory_size': page_size, 'page_sizes': [5, 10, 25], 'directory_term': form.cleaned_data.get('term') if form.is_valid() else None,
        'enrolled_course_count': enrollments.values('course_id').distinct().count(),
        'assessment_count': assessments.count(), 'assessment_course_count': assessments.values('course_id').distinct().count(),
        'attendance_totals': attendance_totals,
        'assigned_faculty': User.objects.filter(teacher_profile__teaching_assignments__in=assignments).distinct()[:3],
        'assessments': assessments.annotate(recorded_count=Count('scores')).order_by('-pk')[:2],
        'dashboard_counts': [('Enrolled students', enrollments.values('student_id').distinct().count()),
            ('Assigned faculty', assignments.values('teacher_id').distinct().count()),
            ('Scores recorded', scores.count()), ('Attendance records', attendance.count())]}


def dashboard_context(user, request=None):
    from academics.grading import attach_course_resit_warnings
    students, scores, attendance = visible_students(user), visible_scores(user), visible_attendance(user)
    enrollments = visible_enrollments(user).exclude(status='withdrawn')
    if user.role == User.Role.STUDENT:
        counts = [('My courses', enrollments.values('course_id').distinct().count()),
                  ('My scores', scores.count()), ('My attendance records', attendance.count())]
    elif user.role == User.Role.TEACHER:
        counts = [('Assigned students', students.count()), ('Scores recorded', scores.count()),
                  ('Attendance records', attendance.count()), ('Assigned classes', visible_assignments(user).count())]
    else:
        counts = [('Students', students.count()), ('Active courses', Course.objects.filter(is_active=True).count()),
                  ('Scores recorded', scores.count()), ('Attendance records', attendance.count())]
    context = {'today': timezone.localdate(), 'dashboard_counts': counts,
        'recent_students': students.order_by('-pk')[:6],
        'assignments': assignment_queryset(user)[:8],
        'assessments': visible_assessments(user).annotate(recorded_count=Count('scores')).order_by('-pk')[:6],
        'recent_scores': scores.order_by('-updated_at')[:6],
        'recent_attendance': attendance.order_by('-session__date', '-updated_at')[:6],
        'enrollments': enrollments.order_by('-term__start_date', 'course__code')[:8],
        'student_profile': students.first() if user.role == User.Role.STUDENT else None, 'setup_actions': []}
    if user.role == User.Role.ADMINISTRATOR and user.is_staff:
        for app, model, label in [('accounts', 'user', 'Accounts'), ('accounts', 'studentprofile', 'Student profiles'),
            ('accounts', 'teacherprofile', 'Teacher profiles'), ('academics', 'academicyear', 'Academic years'),
            ('academics', 'term', 'Terms'), ('academics', 'course', 'Courses'),
            ('academics', 'teachingassignment', 'Teaching assignments'), ('academics', 'enrollment', 'Enrolments'),
            ('academics', 'assessment', 'Assessments')]:
            add = user.has_perm(f'{app}.add_{model}')
            view = user.has_perm(f'{app}.view_{model}') or user.has_perm(f'{app}.change_{model}')
            if add or view:
                context['setup_actions'].append({'label': label,
                    'add_url': reverse(f'admin:{app}_{model}_add') if add else None,
                    'list_url': reverse(f'admin:{app}_{model}_changelist') if view else None})
    if user.role == User.Role.ADMINISTRATOR and request is not None:
        context.update(administrator_directory(user, request.GET))
        from academics.models import AcademicCorrection
        pending = AcademicCorrection.objects.filter(status='pending').select_related('teacher', 'assessment__course', 'session__course')
        context.update(corrections_enabled=True, correction_pending_count=pending.count(), recent_corrections=pending[:5])
    if user.role == User.Role.STUDENT:
        context['enrollments'] = attach_course_resit_warnings(context['enrollments'], scores)
    return context
