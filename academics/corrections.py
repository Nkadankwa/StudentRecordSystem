from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from .correction_models import AcademicCorrection


def record_state(record, fields):
    state = {}
    for field in fields:
        value = getattr(record, field)
        state[field] = str(value.quantize(Decimal('0.01'))) if isinstance(value, Decimal) else value
    state['updated_by_id'] = record.updated_by_id
    return state


@transaction.atomic
def review_correction(user, correction_id, action, reason=''):
    from .models import Score, AttendanceRecord
    if not user.is_active or user.role != User.Role.ADMINISTRATOR:
        raise PermissionDenied
    correction = AcademicCorrection.objects.select_for_update().get(pk=correction_id)
    if correction.status != AcademicCorrection.Status.PENDING:
        raise ValidationError('This correction has already been reviewed.')
    if action not in ('accept', 'revoke'):
        raise ValidationError('Choose an available review action.')
    if action == 'revoke':
        if not reason.strip():
            raise ValidationError('Explain why these changes are being revoked.')
        model = Score if correction.kind == 'scores' else AttendanceRecord
        locked = []
        for change in correction.changes:
            record = model.objects.select_for_update().get(pk=change['pk'])
            fields = [key for key in change['after'] if key != 'updated_by_id']
            if (record.updated_at.isoformat() != change['timestamp'] or
                    record_state(record, fields) != change['after']):
                raise ValidationError('These records have changed again. Revocation was not applied; review the newer correction first.')
            locked.append((record, change))
        for record, change in locked:
            # Restore exactly the prior values without reinterpreting historic grading rules.
            values = dict(change['before'], updated_at=timezone.now())
            if model.objects.filter(pk=record.pk, updated_at=record.updated_at).update(**values) != 1:
                raise ValidationError('A concurrent change prevented revocation. No records were restored.')
    correction.status = AcademicCorrection.Status.REVOKED if action == 'revoke' else AcademicCorrection.Status.ACCEPTED
    correction.reviewed_by = user
    correction.reviewed_at = timezone.now()
    correction.review_reason = reason.strip()
    correction.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_reason'])
    return correction
