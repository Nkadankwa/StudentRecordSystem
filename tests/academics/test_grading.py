from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from academics.grading import prepare_resit
from academics.models import Course, CourseTermGradingPolicy, Term, Assessment, Score, Enrollment
from tests.academics import test_records


class ResitGradingTests(TestCase):
    setUp = test_records.AcademicRecordsTests.setUp
    score = test_records.AcademicRecordsTests.score

    def rule(self, **changes):
        values = dict(course=self.course, term=self.term, pass_percentage=Decimal('50'), method='replace')
        values.update(changes)
        return CourseTermGradingPolicy.objects.create(**values)

    def test_no_invented_threshold_or_unassigned_entry(self):
        score = self.score(value=Decimal('30'))
        self.assertFalse(score.can_resit)
        with self.assertRaises(ValidationError):
            prepare_resit(score, Decimal('70'), self.teacher.user)
        self.rule()
        with self.assertRaises(PermissionDenied):
            prepare_resit(score, Decimal('70'), self.admin)

    def test_preserves_original_and_identifies_failed_resit(self):
        self.rule()
        score = self.score(value=Decimal('30'))
        prepare_resit(score, Decimal('40'), self.teacher.user)
        score.save()
        self.assertEqual(score.value, Decimal('30'))
        self.assertEqual(score.effective_value, Decimal('40'))
        self.assertEqual(score.outcome, 'Fail — course resit required')
        self.assertFalse(score.can_resit)

    def test_methods_cap_bounds_and_eligibility(self):
        rule = self.rule(method='weighted', resit_weight=Decimal('75'), cap_percentage=Decimal('60'))
        score = self.score(value=Decimal('30'))
        prepare_resit(score, Decimal('90'), self.teacher.user)
        self.assertEqual(score.effective_value, Decimal('60'))
        self.assertEqual(score.outcome, 'Pass · resit')
        for value in (Decimal('-1'), Decimal('101'), Decimal('NaN')):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                prepare_resit(self.score(value=Decimal('30')), value, self.teacher.user)
        with self.assertRaises(ValidationError):
            prepare_resit(self.score(value=Decimal('50')), Decimal('90'), self.teacher.user)
        rule.method, rule.cap_percentage = 'higher', None
        rule.save()
        score = prepare_resit(self.score(value=Decimal('30')), Decimal('20'), self.teacher.user)
        self.assertEqual(score.effective_value, Decimal('30'))

    def test_saved_rules_and_maximum_do_not_regrade_history(self):
        rule = self.rule()
        score = prepare_resit(self.score(value=Decimal('30')), Decimal('60'), self.teacher.user)
        score.save()
        rule.pass_percentage, rule.method = Decimal('90'), 'weighted'
        rule.save()
        self.assessment.maximum_score = Decimal('200')
        self.assessment.save()
        score.refresh_from_db()
        self.assertEqual(score.effective_percentage, Decimal('60'))
        self.assertEqual(score.outcome, 'Pass · resit')
        prepare_resit(score, None, self.teacher.user)
        self.assertEqual(score.resit_value, Decimal('60'))
        self.assertEqual(score.resit_effective_value, Decimal('60'))

    def test_policy_is_unique_course_and_term_and_invalid_cap_rejected(self):
        self.rule()
        with self.assertRaises(ValidationError):
            self.rule()
        with self.assertRaises(ValidationError):
            self.rule(cap_percentage=Decimal('40'))

    def test_other_course_rule_never_enables_resit(self):
        course = Course.objects.create(code='OTHER', title='Other course')
        CourseTermGradingPolicy.objects.create(course=course, term=self.term, pass_percentage=Decimal('50'), method='replace')
        self.assertFalse(self.score(value=Decimal('30')).can_resit)

    def test_same_course_other_term_rule_and_failure_are_isolated(self):
        from datetime import date
        from academics.grading import attach_course_resit_warnings
        from accounts.policies import visible_scores
        self.rule()
        prepare_resit(self.score(value=Decimal('30')), Decimal('40'), self.teacher.user).save()
        other_term = Term.objects.create(academic_year=self.year, name='Second term', start_date=date(2030, 7, 1), end_date=date(2030, 12, 31))
        other_assessment = Assessment.objects.create(course=self.course, term=other_term, title='Other term assessment', maximum_score=Decimal('100'))
        other_score = Score(assessment=other_assessment, student=self.student, value=Decimal('30'), updated_by=self.teacher.user)
        self.assertFalse(other_score.can_resit)
        other_enrollment = Enrollment.objects.create(student=self.student, course=self.course, term=other_term)
        rows = attach_course_resit_warnings([self.enrollment, other_enrollment], visible_scores(self.student.user))
        self.assertTrue(rows[0].course_resit_required)
        self.assertFalse(rows[1].course_resit_required)

    def test_same_rule_can_be_disabled_without_erasing_history(self):
        rule = self.rule()
        score = prepare_resit(self.score(value=Decimal('30')), Decimal('60'), self.teacher.user)
        score.save()
        rule.enabled = False
        rule.save()
        self.assertFalse(self.score(value=Decimal('30')).can_resit)
        self.assertEqual(score.outcome, 'Pass · resit')

    def test_manually_supplied_resit_without_snapshot_rejected(self):
        with self.assertRaises(ValidationError):
            self.score(value=Decimal('30'), resit_value=Decimal('70')).save()

    def test_failed_resit_warning_in_profile_record_dashboard_keeps_enrollment_status(self):
        self.rule()
        score = prepare_resit(self.score(value=Decimal('30')), Decimal('40'), self.teacher.user)
        score.save()
        self.client.force_login(self.student.user)
        for url in (reverse('students:detail', args=[self.student.pk]),
                    reverse('academics:record', args=[self.student.pk]),
                    reverse('accounts:student_home')):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, 'Fail — course resit required')
                self.assertContains(response, 'Active')
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, 'active')

    def test_course_warning_respects_viewer_scope(self):
        from accounts.models import TeacherProfile, User
        from accounts.policies import visible_scores
        from academics.grading import attach_course_resit_warnings
        self.rule()
        prepare_resit(self.score(value=Decimal('30')), Decimal('40'), self.teacher.user).save()
        outsider = User.objects.create_user(username='outside-teacher', role=User.Role.TEACHER)
        TeacherProfile.objects.create(user=outsider, employee_number='T-OUTSIDE')
        rows = attach_course_resit_warnings([self.enrollment], visible_scores(outsider))
        self.assertFalse(rows[0].course_resit_required)
        rows = attach_course_resit_warnings([self.enrollment], visible_scores(self.teacher.user))
        self.assertTrue(rows[0].course_resit_required)
