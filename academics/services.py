from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.core import signing
from django.utils import timezone

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
        identity = ['scores', assessment.pk, course_id, term_id, str(assessment.maximum_score)]
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
        if type(record).objects.filter(pk=record.pk, updated_at=previous_timestamp).update(**values) != 1:
            raise ValidationError('A concurrent edit was detected. Reload before saving.')
    else:
        record.save()


@transaction.atomic
def save_scores(user, assessment, rows, *, revision):
    if not visible_assessments(user).filter(pk=assessment.pk).exists():
        raise PermissionDenied
    assessment = Assessment.objects.select_for_update().get(pk=assessment.pk)
    check_revision(revision, user, assessment=assessment)
    enrollments = list(roster(assessment.course_id, assessment.term_id).select_for_update())
    validate_roster(rows, enrollments)
    for row in rows:
        if row['value'] is None:
            continue
        score = Score.objects.select_for_update().filter(assessment=assessment, student_id=row['student']).first()
        if score is None:
            score = Score(assessment=assessment, student_id=row['student'])
        previous = score.updated_at if score.pk else None
        score.value, score.remarks, score.updated_by = row['value'], row['remarks'], user
        persist_record(score, previous, ('value', 'remarks'))


@transaction.atomic
def save_attendance(user, assignment, session_data, rows, session=None, *, revision):
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
    for row in rows:
        record = AttendanceRecord.objects.select_for_update().filter(session=session, student_id=row['student']).first()
        if record is None:
            record = AttendanceRecord(session=session, student_id=row['student'])
        previous = record.updated_at if record.pk else None
        record.status, record.remarks, record.updated_by = row['status'], row['remarks'], user
        persist_record(record, previous, ('status', 'remarks'))
    return session
