from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, OperationalError
from django.db.models import Count, Q
from django.forms.utils import ErrorList
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import StudentProfile, User
from accounts.policies import (roles_required, visible_assessments, visible_assignments,
    visible_scores, visible_attendance, visible_enrollments, visible_students, scoped_academic)
from .forms import RecordFilterForm, ScoreFormSet, AttendanceFormSet, AttendanceSessionForm
from .models import Assessment, AttendanceSession
from .services import roster, save_scores, save_attendance, make_revision


def scoped_object(model, queryset, pk):
    try:
        pk = int(pk)
    except (ValueError, TypeError):
        from django.http import Http404
        raise Http404
    get_object_or_404(model, pk=pk)
    obj = queryset.filter(pk=pk).first()
    if obj is None:
        raise PermissionDenied
    return obj


def filtered_records(request, records, relation):
    form = RecordFilterForm(request.GET, records=records, relation=relation)
    if form.is_valid():
        for name in ('course', 'term'):
            if form.cleaned_data[name]:
                records = records.filter(**{f'{relation}__{name}': form.cleaned_data[name]})
    else:
        records = records.none()
    return form, records


def pagination(request, records, parameter='page'):
    page = Paginator(records, 50).get_page(request.GET.get(parameter))
    query = request.GET.copy()
    query.pop(parameter, None)
    return {'page': page, 'parameter': parameter, 'query': query.urlencode()}


@roles_required(*User.Role.values)
def scores(request):
    form, records = filtered_records(request, visible_scores(request.user), 'assessment')
    records = records.order_by('assessment__term__start_date', 'assessment__course__code', 'assessment__title', 'student__student_number')
    pages = pagination(request, records)
    entries = pagination(request, visible_assessments(request.user).order_by('-term__start_date', 'pk'), 'entries')
    return render(request, 'academics/scores.html', {'filter_form': form, 'records': pages['page'].object_list,
        'pagination': pages, 'entries_pagination': entries, 'assessments': entries['page'].object_list})


@roles_required(User.Role.TEACHER, User.Role.ADMINISTRATOR)
def score_entry(request, pk):
    assessment = scoped_object(Assessment, visible_assessments(request.user), pk)
    enrolled = list(roster(assessment.course_id, assessment.term_id))
    existing = {s.student_id: s for s in assessment.scores.all()}
    initial = [{'student': e.student_id, 'value': existing[e.student_id].value if e.student_id in existing else None,
                'remarks': existing[e.student_id].remarks if e.student_id in existing else ''} for e in enrolled]
    forms = ScoreFormSet(request.POST if request.method == 'POST' else None, initial=initial)
    if request.method == 'POST' and forms.is_valid():
        try:
            save_scores(request.user, assessment, forms.cleaned_data, revision=request.POST.get('revision', ''))
        except (ValidationError, IntegrityError, OperationalError) as error:
            forms._non_form_errors = ErrorList(error.messages if isinstance(error, ValidationError) else ['A record changed while saving. Reload and try again.'])
        else:
            messages.success(request, 'Scores saved.')
            return redirect('academics:scores')
    return render(request, 'academics/entry.html', {'title': f'Scores: {assessment.title}', 'formset': forms,
        'rows': list(zip(forms.forms, [e.student for e in enrolled])), 'assessment': assessment,
        'revision': request.POST.get('revision', '') if request.method == 'POST' else make_revision(request.user, assessment=assessment)})


def attendance_totals(records):
    return records.order_by().values('session__term_id', 'session__term__academic_year__name',
        'session__term__name', 'session__course__code').annotate(
        present=Count('pk', filter=Q(status='present')),
        absent=Count('pk', filter=Q(status='absent')),
        late=Count('pk', filter=Q(status='late')),
        excused=Count('pk', filter=Q(status='excused')),
    ).order_by('session__term__academic_year__name', 'session__term__name', 'session__course__code')


@roles_required(*User.Role.values)
def attendance(request):
    form, records = filtered_records(request, visible_attendance(request.user), 'session')
    records = records.order_by('session__term__start_date', 'session__course__code', '-session__date', 'student__student_number')
    sessions = scoped_academic(AttendanceSession.objects.select_related('course', 'term__academic_year', 'teacher__user'), request.user, 'course_id', 'term_id')
    pages = pagination(request, records)
    entries = pagination(request, sessions.order_by('-date', 'pk'), 'entries')
    return render(request, 'academics/attendance.html', {'filter_form': form, 'records': pages['page'].object_list,
        'pagination': pages, 'entries_pagination': entries,
        'totals': attendance_totals(records), 'sessions': entries['page'].object_list})


@roles_required(User.Role.TEACHER, User.Role.ADMINISTRATOR)
def attendance_entry(request, pk=None):
    assignment = None
    session = None
    if pk is not None:
        session = scoped_object(AttendanceSession, scoped_academic(AttendanceSession.objects.all(), request.user, 'course_id', 'term_id'), pk)
        assignment = visible_assignments(request.user).filter(course=session.course, term=session.term).first()
        if assignment is None:
            raise PermissionDenied
    if request.method == 'POST':
        session_form = AttendanceSessionForm(request.POST, user=request.user)
        session_form.is_valid()
        selected = session_form.cleaned_data.get('assignment')
        if session and selected and (selected.course_id != session.course_id or selected.term_id != session.term_id):
            raise PermissionDenied
        assignment = selected
    else:
        if not assignment and request.GET.get('assignment'):
            from .models import TeachingAssignment
            assignment = scoped_object(TeachingAssignment, visible_assignments(request.user), request.GET['assignment'])
        session_form = AttendanceSessionForm(user=request.user, initial={'assignment': assignment,
            'date': session.date if session else (timezone.localdate() if assignment and assignment.term.start_date <= timezone.localdate() <= assignment.term.end_date else None), 'lesson_label': session.lesson_label if session else ''})
    enrolled = list(roster(assignment.course_id, assignment.term_id)) if assignment else []
    existing = {r.student_id: r for r in session.records.all()} if session else {}
    initial = [{'student': e.student_id, 'status': existing[e.student_id].status if e.student_id in existing else '',
                'remarks': existing[e.student_id].remarks if e.student_id in existing else ''} for e in enrolled]
    forms = AttendanceFormSet(request.POST if request.method == 'POST' else None, initial=initial)
    if request.method == 'POST' and session_form.is_valid() and forms.is_valid():
        try:
            if not assignment or not enrolled:
                raise ValidationError('Choose a course with enrolled students before saving attendance.')
            if session and (session_form.cleaned_data['date'] != session.date or session_form.cleaned_data['lesson_label'] != session.lesson_label):
                raise ValidationError('Existing session dates and lesson labels cannot be changed here.')
            save_attendance(request.user, assignment, session_form.cleaned_data, forms.cleaned_data, session=session, revision=request.POST.get('revision', ''))
        except (ValidationError, IntegrityError, OperationalError) as error:
            forms._non_form_errors = ErrorList(error.messages if isinstance(error, ValidationError) else ['A duplicate session or record was detected. Reload and try again.'])
        else:
            messages.success(request, 'Attendance saved.')
            return redirect('academics:attendance')
    return render(request, 'academics/entry.html', {'title': 'Update attendance' if session else 'Take attendance',
        'session_form': session_form, 'formset': forms, 'rows': list(zip(forms.forms, [e.student for e in enrolled])),
        'assignment': assignment, 'is_attendance': True, 'session': session,
        'revision': request.POST.get('revision', '') if request.method == 'POST' else (make_revision(request.user, assignment=assignment, session=session) if assignment else '')})


@roles_required(*User.Role.values)
def student_record(request, pk):
    profile = scoped_object(StudentProfile, visible_students(request.user), pk)
    scores = visible_scores(request.user).filter(student=profile).order_by('assessment__term__start_date', 'assessment__course__code', 'assessment__title')
    attendance = visible_attendance(request.user).filter(student=profile)
    enrollments = visible_enrollments(request.user).filter(student=profile)
    return render(request, 'academics/record.html', {'profile': profile, 'records': scores,
        'enrollments': enrollments, 'totals': attendance_totals(attendance)})
