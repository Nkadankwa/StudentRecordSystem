"""Decimal-only resit calculations. Stored snapshots keep historical results stable."""
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import PermissionDenied, ValidationError

from accounts.models import User


def policy_for(score):
    from .grading_models import CourseTermGradingPolicy
    cached = getattr(score.assessment.course, '_prefetched_objects_cache', {}).get('grading_policies')
    if cached is not None:
        return next((policy for policy in cached if policy.term_id == score.assessment.term_id and policy.enabled), None)
    return CourseTermGradingPolicy.objects.filter(course_id=score.assessment.course_id, term_id=score.assessment.term_id, enabled=True).first()


def eligible_for_resit(score):
    policy = policy_for(score)
    return bool(policy and score.value is not None and score.value * 100 / score.assessment.maximum_score < policy.pass_percentage)


def calculate(original, resit, snapshot):
    maximum = Decimal(snapshot['maximum_score'])
    method = snapshot['method']
    if method == 'replace':
        result = resit
    elif method == 'higher':
        result = max(original, resit)
    elif method == 'weighted':
        weight = Decimal(snapshot['resit_weight']) / 100
        result = original * (1 - weight) + resit * weight
    else:
        raise ValidationError({'resit_value': 'The saved resit calculation is invalid.'})
    if snapshot.get('cap_percentage') is not None:
        result = min(result, maximum * Decimal(snapshot['cap_percentage']) / 100)
    return result.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def prepare_resit(score, resit_value, user):
    from .models import TeachingAssignment
    if user.role != User.Role.TEACHER or not user.is_active or not TeachingAssignment.objects.filter(teacher__user=user, course_id=score.assessment.course_id, term_id=score.assessment.term_id).exists():
        raise PermissionDenied('Only the assigned teacher can enter a resit.')
    if resit_value in (None, ''):
        resit_value = score.resit_value
    if resit_value is None:
        return score
    try:
        resit = Decimal(str(resit_value))
    except (ValueError, TypeError, ArithmeticError):
        raise ValidationError({'resit_value': 'Enter a valid resit score.'})
    snapshot = dict(score.resit_policy_snapshot or {})
    if not snapshot:
        policy = policy_for(score)
        if not policy or not eligible_for_resit(score):
            raise ValidationError({'resit_value': 'A resit is available only below the configured course and term pass threshold.'})
        snapshot = {'policy_id': policy.pk, 'course_id': score.assessment.course_id, 'term_id': score.assessment.term_id,
                    'method': policy.method, 'pass_percentage': str(policy.pass_percentage),
                    'resit_weight': str(policy.resit_weight), 'cap_percentage': str(policy.cap_percentage) if policy.cap_percentage is not None else None,
                    'maximum_score': str(score.assessment.maximum_score)}
    maximum = Decimal(snapshot['maximum_score'])
    if not resit.is_finite() or resit < 0 or resit > maximum:
        raise ValidationError({'resit_value': f'Resit must be between 0 and {maximum}.'})
    snapshot['original_value'] = str(score.value)
    score.resit_value = resit
    score.resit_policy_snapshot = snapshot
    score.resit_effective_value = calculate(score.value, resit, snapshot)
    return score


def validate_score_resit(score):
    if score.resit_value is None:
        if score.resit_policy_snapshot or score.resit_effective_value is not None:
            raise ValidationError({'resit_value': 'A resit calculation requires a resit score.'})
        return
    try:
        snapshot = score.resit_policy_snapshot
        maximum = Decimal(snapshot['maximum_score'])
        original = Decimal(snapshot['original_value'])
        resit = Decimal(str(score.resit_value))
        value = Decimal(str(score.value))
        valid = (maximum.is_finite() and original.is_finite() and resit.is_finite() and value.is_finite()
                 and maximum > 0 and 0 <= resit <= maximum
                 and snapshot['course_id'] == score.assessment.course_id
                 and snapshot['term_id'] == score.assessment.term_id
                 and original == value
                 and original * 100 / maximum < Decimal(snapshot['pass_percentage'])
                 and calculate(original, resit, snapshot) == score.resit_effective_value)
    except (KeyError, TypeError, ValueError, ArithmeticError):
        valid = False
    if not valid:
        raise ValidationError({'resit_value': 'The resit result needs a valid saved grading rule and an eligible original score.'})


def attach_course_resit_warnings(enrollments, scores):
    """Attach outcomes using only scores already scoped to the current viewer."""
    rows = list(enrollments)
    if not rows:
        return rows
    keys = {(row.student_id, row.course_id, row.term_id) for row in rows}
    failed = set()
    candidates = scores.filter(resit_value__isnull=False,
        student_id__in={key[0] for key in keys},
        assessment__course_id__in={key[1] for key in keys},
        assessment__term_id__in={key[2] for key in keys})
    for score in candidates:
        key = (score.student_id, score.assessment.course_id, score.assessment.term_id)
        if key in keys and score.is_course_resit_required:
            failed.add(key)
    for row in rows:
        row.course_resit_required = (row.student_id, row.course_id, row.term_id) in failed
    return rows
