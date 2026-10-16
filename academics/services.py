from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.core import signing
from django.utils import timezone

from accounts.models import User
from .correction_models import AcademicCorrection
from .corrections import record_state

from accounts.policies import visible_assessments, visible_assignments
from .models import AttendanceRecord, AttendanceSession, Enrollment, Score, Assessment


def roster(course_id, term_id):
    return Enrollment.objects.filter(course_id=course_id, term_id=term_id).exclude(status=Enrollment.Status.WITHDRAWN).select_related('student__user').order_by('student__student_number')


def validate_roster(rows, enrollments):
    expected = {e.student_id for e in enrollments}
    submitted = [row['student'] for row in rows]
    if len(submitted) != len(set(submitted)) or set(submitted) != expected:
        raise ValidationError('The roster changed or contains invalid students. Reload the page before saving.')


def revision_state(user, *, assessment=None, assignment=None, session=None):
    if assessment:
        course_id, term_id = assessment.course_id, assessment.term_id
        records = Score.objects.filter(assessment=assessment)
        identity = ['scores', assessment.pk, course_id, term_id, format(assessment.maximum_score, '.2f')]
    else:
        course_id, term_id = assignment.course_id, assignment.term_id
        records = AttendanceRecord.objects.filter(session=session) if session else AttendanceRecord.objects.none()
        identity = ['attendance', assignment.pk, course_id, term_id, session.pk if session else None,
                    str(session.date) if session else None, session.lesson_label if session else None]
    return {'user': user.pk, 'identity': identity,
            'roster': list(roster(course_id, term_id).values_list('pk', 'student_id', 'status')),
            'records': [[r.student_id, r.updated_at.isoformat()] for r in records.order_by('student_id')]}


def make_revision(user, **objects):
    return signing.dumps(revision_state(user, **objects), salt='academic-edit', compress=True)


def check_revision(token, user, **objects):
    try:
        snapshot = signing.loads(token, salt='academic-edit', max_age=3600)
    except (signing.BadSignature, TypeError):
        raise ValidationError('This form is expired or invalid. Reload before saving.')
    current = revision_state(user, **objects)
    # JSON converts tuple roster entries to lists.
    current['roster'] = [list(item) for item in current['roster']]
    if snapshot != current:
        raise ValidationError('These records changed since you opened the form. Reload before saving; your changes were not applied.')


def persist_record(record, previous_timestamp, fields):
    if record.pk:
        record.full_clean()
        values = {name: getattr(record, name) for name in fields}
        values.update(updated_by_id=record.updated_by_id, updated_at=timezone.now())
        record.updated_at = values['updated_at']
        if type(record).objects.filter(pk=record.pk, updated_at=previous_timestamp).update(**values) != 1:
            raise ValidationError('A concurrent edit was detected. Reload before saving.')
    else:
        record.save()


@transaction.atomic
def save_scores(user, assessment, rows, *, revision, reason=""):
    if not user.is_active or user.role != User.Role.TEACHER:
        raise PermissionDenied
    if not visible_assessments(user).filter(pk=assessment.pk).exists():
        raise PermissionDenied
    assessment = Assessment.objects.select_for_update().get(pk=assessment.pk)
    check_revision(revision, user, assessment=assessment)
    enrollments = list(roster(assessment.course_id, assessment.term_id).select_for_update())
    validate_roster(rows, enrollments)
    changes = []
    fields = ('value', 'remarks', 'resit_value', 'resit_policy_snapshot', 'resit_effective_value')
    for row in rows:
        if row['value'] is None:
            continue
        score = Score.objects.select_for_update().filter(assessment=assessment, student_id=row['student']).first()
        if score is None:
            score = Score(assessment=assessment, student_id=row['student'])
        previous = score.updated_at if score.pk else None
        before = record_state(score, fields) if score.pk else None
        score.value, score.remarks = row['value'], row['remarks']
        from .grading import prepare_resit
        prepare_resit(score, row.get('resit_value'), user)
        if before and all(before[name] == record_state(score, fields)[name] for name in fields):
            continue
        if before and not reason.strip():
            raise ValidationError('Explain the reason for changing submitted scores.')
        score.updated_by = user
        persist_record(score, previous, fields)
        if before:
            score.refresh_from_db()
            changes.append({'pk': score.pk, 'student': str(score.student), 'before': before,
                            'after': record_state(score, fields), 'fields': [name for name in fields if before[name] != record_state(score, fields)[name]], 'timestamp': score.updated_at.isoformat()})
    if changes:
        AcademicCorrection.objects.create(teacher=user, kind='scores', assessment=assessment,
                                          reason=reason.strip(), changes=changes)


@transaction.atomic
def save_attendance(user, assignment, session_data, rows, session=None, *, revision, reason=""):
    if not user.is_active or user.role != User.Role.TEACHER:
        raise PermissionDenied
    if not visible_assignments(user).filter(pk=assignment.pk).exists():
        raise PermissionDenied
    if session is not None:
        session = AttendanceSession.objects.select_for_update().get(pk=session.pk)
    check_revision(revision, user, assignment=assignment, session=session)
    enrollments = list(roster(assignment.course_id, assignment.term_id).select_for_update())
    validate_roster(rows, enrollments)
    if session is None:
        session = AttendanceSession(course=assignment.course, term=assignment.term, teacher=assignment.teacher,
                                    date=session_data['date'], lesson_label=session_data['lesson_label'])
        session.save()
    else:
        if session.course_id != assignment.course_id or session.term_id != assignment.term_id:
            raise PermissionDenied
    changes = []
    fields = ('status', 'remarks')
    for row in rows:
        record = AttendanceRecord.objects.select_for_update().filter(session=session, student_id=row['student']).first()
        if record is None:
            record = AttendanceRecord(session=session, student_id=row['student'])
        previous = record.updated_at if record.pk else None
        before = record_state(record, fields) if record.pk else None
        record.status, record.remarks = row['status'], row['remarks']
        if before and all(before[name] == record_state(record, fields)[name] for name in fields):
            continue
        if before and not reason.strip():
            raise ValidationError('Explain the reason for changing submitted attendance.')
        record.updated_by = user
        persist_record(record, previous, fields)
        if before:
            record.refresh_from_db()
            changes.append({'pk': record.pk, 'student': str(record.student), 'before': before,
                            'after': record_state(record, fields), 'fields': [name for name in fields if before[name] != record_state(record, fields)[name]], 'timestamp': record.updated_at.isoformat()})
    if changes:
        AcademicCorrection.objects.create(teacher=user, kind='attendance', session=session,
                                          reason=reason.strip(), changes=changes)
    return session
