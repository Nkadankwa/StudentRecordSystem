from datetime import date

from django.contrib import admin
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.core.exceptions import ValidationError
from django.forms import modelform_factory
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from academics.models import AcademicYear, Course, Term


class AcademicSetupTests(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(
            name='Test year', start_date=date(2030, 9, 1), end_date=date(2031, 8, 31),
        )

    def term(self, **changes):
        data = dict(academic_year=self.year, name='First term', start_date=date(2030, 9, 1), end_date=date(2030, 12, 20))
        data.update(changes)
        return Term(**data)

    def test_valid_periods_and_display_names(self):
        term = self.term()
        term.full_clean()
        term.save()
        self.assertEqual(str(self.year), 'Test year')
        self.assertEqual(str(term), 'Test year — First term')
        self.assertEqual(self.year.terms.get(), term)

    def test_date_order_validated_and_constrained(self):
        for model in (self.year, self.term()):
            with self.subTest(model=type(model).__name__):
                model.end_date = model.start_date
                with self.assertRaises(ValidationError):
                    model.full_clean()
                with self.assertRaises(IntegrityError), transaction.atomic():
                    model.save()

    def test_terms_must_fit_inside_year(self):
        for changes in (
            {'start_date': date(2030, 8, 31)},
            {'end_date': date(2031, 9, 1)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.term(**changes).full_clean()

    def test_year_boundaries_are_allowed(self):
        self.term(start_date=self.year.start_date, end_date=self.year.end_date).full_clean()

    def test_year_cannot_be_shortened_past_existing_term(self):
        self.term().save()
        self.year.start_date = date(2030, 10, 1)
        with self.assertRaises(ValidationError):
            self.year.full_clean()

    def test_year_name_is_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AcademicYear.objects.create(name=self.year.name, start_date=date(2032, 1, 1), end_date=date(2032, 12, 31))

    def test_term_name_is_unique_within_year(self):
        self.term().save()
        with self.assertRaises(ValidationError):
            self.term().full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.term().save()
        other_year = AcademicYear.objects.create(name='Other year', start_date=date(2030, 9, 1), end_date=date(2031, 8, 31))
        self.term(academic_year=other_year).full_clean()

    def test_year_with_terms_cannot_be_deleted(self):
        self.term().save()
        with self.assertRaises(ProtectedError):
            self.year.delete()

    def test_course_code_normalization_and_uniqueness(self):
        course = Course(code=' demo101 ', title='Example course')
        course.full_clean()
        course.save()
        self.assertEqual(str(course), 'DEMO101 — Example course')
        with self.assertRaises(ValidationError):
            Course(code='demo101', title='Duplicate example').full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Course.objects.create(code='DEMO101', title='Duplicate example')
        with self.assertRaises(ValidationError):
            Course(code='   ', title='Example course').full_clean()

    def test_ordering(self):
        later = AcademicYear.objects.create(name='Later year', start_date=date(2032, 9, 1), end_date=date(2033, 8, 31))
        self.assertEqual(list(AcademicYear.objects.all()), [later, self.year])
        late_term = self.term(name='Second term', start_date=date(2031, 1, 1), end_date=date(2031, 6, 1))
        late_term.save()
        early_term = self.term()
        early_term.save()
        self.assertEqual(list(Term.objects.all()), [early_term, late_term])
        Course.objects.create(code='Z', title='Last')
        Course.objects.create(code='A', title='First')
        self.assertEqual(list(Course.objects.values_list('code', flat=True)), ['A', 'Z'])

    def test_admin_forms_reject_invalid_periods(self):
        Form = modelform_factory(Term, fields=('academic_year', 'name', 'start_date', 'end_date'))
        form = Form(data={'academic_year': self.year.pk, 'name': 'First term', 'start_date': '2030-08-31', 'end_date': '2030-12-20'})
        self.assertFalse(form.is_valid())
        self.assertIn('start_date', form.errors)
        for model in (AcademicYear, Term, Course):
            self.assertIn(model, admin.site._registry)

    def test_invalid_year_reference_reports_validation_error(self):
        term = Term(academic_year_id=self.year.pk + 999, name='Invalid reference', start_date=date(2030, 9, 1), end_date=date(2030, 12, 20))
        with self.assertRaises(ValidationError):
            term.full_clean()


class AcademicAdminTests(TestCase):
    def setUp(self):
        user = User.objects.create_superuser(username='academic-admin-test', password=None)
        self.client.force_login(user)

    def test_administrator_can_create_year_term_and_course(self):
        response = self.client.post(reverse('admin:academics_academicyear_add'), {
            'name': 'Admin test year', 'start_date': '2030-09-01',
            'end_date': '2031-08-31', 'is_active': 'on', '_save': 'Save',
        })
        self.assertEqual(response.status_code, 302)
        year = AcademicYear.objects.get(name='Admin test year')
        response = self.client.post(reverse('admin:academics_term_add'), {
            'academic_year': year.pk, 'name': 'First term', 'start_date': '2030-09-01',
            'end_date': '2030-12-20', '_save': 'Save',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(year.terms.count(), 1)
        response = self.client.post(reverse('admin:academics_course_add'), {
            'code': 'example101', 'title': 'Admin example course',
            'description': '', 'is_active': 'on', '_save': 'Save',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Course.objects.filter(code='EXAMPLE101').exists())

    def test_admin_rejects_term_outside_year(self):
        year = AcademicYear.objects.create(name='Admin test year', start_date=date(2030, 9, 1), end_date=date(2031, 8, 31))
        response = self.client.post(reverse('admin:academics_term_add'), {
            'academic_year': year.pk, 'name': 'Invalid term', 'start_date': '2030-08-01',
            'end_date': '2030-12-20', '_save': 'Save',
        })
        self.assertContains(response, 'Start date must fall within the academic year.')
        self.assertFalse(Term.objects.exists())
