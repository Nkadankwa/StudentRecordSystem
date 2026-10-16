from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from academics.correction_models import AcademicCorrection
from academics.corrections import review_correction
from academics.services import make_revision, save_scores, save_attendance
from . import test_records


class CorrectionTests(TestCase):
    setUp = test_records.AcademicRecordsTests.setUp

    def save_score(self, value, reason='', user=None):
        user = user or self.teacher.user
        save_scores(user, self.assessment, [{'student': self.student.pk, 'value': Decimal(value), 'remarks': ''}],
                    revision=make_revision(user, assessment=self.assessment), reason=reason)

    def test_initial_entry_is_teacher_only_and_correction_requires_reason(self):
        with self.assertRaises(PermissionDenied):
            self.save_score('50', user=self.admin)
        self.save_score('50')
        with self.assertRaises(ValidationError):
            self.save_score('60')
        self.assertEqual(self.assessment.scores.get().value, Decimal('50'))
        self.assertFalse(AcademicCorrection.objects.exists())
        self.save_score('50')
        self.assertFalse(AcademicCorrection.objects.exists())

    def test_correction_applies_immediately_and_admin_can_restore_original(self):
        self.save_score('50')
        self.save_score('60', 'Checked original marking sheet.')
        correction = AcademicCorrection.objects.get()
        self.assertEqual(self.assessment.scores.get().value, Decimal('60'))
        self.assertEqual(correction.changes[0]['before']['value'], '50.00')
        with self.assertRaises(PermissionDenied):
            review_correction(self.teacher.user, correction.pk, 'revoke', 'No')
        with self.assertRaises(ValidationError):
            review_correction(self.admin, correction.pk, 'revoke')
        review_correction(self.admin, correction.pk, 'revoke', 'Original marking does not support this change.')
        self.assertEqual(self.assessment.scores.get().value, Decimal('50'))
        correction.refresh_from_db()
        self.assertEqual(correction.status, 'revoked')

    def test_stale_revocation_does_not_overwrite_later_correction(self):
        self.save_score('50')
        self.save_score('60', 'First verification')
        first = AcademicCorrection.objects.get()
        self.save_score('70', 'Second verification')
        with self.assertRaises(ValidationError):
            review_correction(self.admin, first.pk, 'revoke', 'Unsupported')
        self.assertEqual(self.assessment.scores.get().value, Decimal('70'))

    def test_attendance_changes_are_logged_and_reversible(self):
        data = {'date': self.session.date, 'lesson_label': self.session.lesson_label}
        def save(status, reason=''):
            save_attendance(self.teacher.user, self.assignment, data,
                [{'student': self.student.pk, 'status': status, 'remarks': ''}], session=self.session,
                revision=make_revision(self.teacher.user, assignment=self.assignment, session=self.session), reason=reason)
        save('present')
        with self.assertRaises(ValidationError):
            save('absent')
        save('late', 'Arrival time verified against class register.')
        correction = AcademicCorrection.objects.get()
        review_correction(self.admin, correction.pk, 'revoke', 'Register contradicts submitted reason.')
        self.assertEqual(self.session.records.get().status, 'present')

    def test_admin_cannot_use_entry_endpoints_or_admin_write_pages(self):
        self.client.force_login(self.admin)
        for url in [reverse('academics:score_entry', args=[self.assessment.pk]),
                    reverse('academics:attendance_new'), reverse('admin:academics_score_add'),
                    reverse('admin:academics_attendancerecord_add'), reverse('admin:academics_attendancesession_add')]:
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_teacher_can_view_own_correction_but_cannot_review_it(self):
        self.save_score('50')
        self.save_score('60', 'Verified original answer sheet.')
        correction = AcademicCorrection.objects.get()
        self.client.force_login(self.teacher.user)
        url = reverse('academics:correction_detail', args=[correction.pk])
        self.assertContains(self.client.get(url), 'Verified original answer sheet.')
        self.assertEqual(self.client.post(url, {'action': 'accept'}).status_code, 403)
        self.client.force_login(self.student.user)
        self.assertEqual(self.client.get(url).status_code, 403)
