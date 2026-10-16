from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from accounts.models import User

from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import models


class AcademicYear(models.Model):
    name = models.CharField(max_length=50, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ('-start_date', 'name')
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gt=models.F('start_date')),
                name='academics_year_dates_in_order',
            ),
        ]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date:
            if self.end_date <= self.start_date:
                raise ValidationError({'end_date': 'End date must be after start date.'})
            if self.pk and not self._state.adding:
                outside = self.terms.filter(
                    models.Q(start_date__lt=self.start_date) | models.Q(end_date__gt=self.end_date)
                )
                if outside.exists():
                    raise ValidationError('The academic year must contain all of its existing terms.')

    def __str__(self):
        return self.name


class Term(models.Model):
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name='terms')
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ('start_date', 'name')
        constraints = [
            models.UniqueConstraint(fields=('academic_year', 'name'), name='academics_unique_term_name_per_year'),
            models.CheckConstraint(
                condition=models.Q(end_date__gt=models.F('start_date')),
                name='academics_term_dates_in_order',
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            errors['end_date'] = 'End date must be after start date.'
        if self.academic_year_id:
            try:
                year = self.academic_year
            except AcademicYear.DoesNotExist:
                raise ValidationError({'academic_year': 'Select a valid academic year.'})
            if self.start_date and not year.start_date <= self.start_date <= year.end_date:
                errors['start_date'] = 'Start date must fall within the academic year.'
            if self.end_date and not year.start_date <= self.end_date <= year.end_date:
                errors['end_date'] = 'End date must fall within the academic year.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.academic_year} — {self.name}'


class Course(models.Model):
    code = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('code',)

    def clean(self):
        super().clean()
        self.code = self.code.strip().upper()
        if not self.code:
            raise ValidationError({'code': 'Enter a course code.'})

    def __str__(self):
        return f'{self.code} — {self.title}'


class ValidatedModel(models.Model):
    """Normal saves validate cross-table rules; bulk writes bypass validation."""
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


def finite_decimal(value):
    # full_clean reports malformed decimal fields; clean must not mask that error.
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def related(instance, field):
    try:
        return getattr(instance, field)
    except ObjectDoesNotExist:
        raise ValidationError({field: 'Select a valid related record.'})


def check_profile(instance, field, role):
    if getattr(instance, field + '_id'):
        try:
            profile = getattr(instance, field)
        except ObjectDoesNotExist:
            raise ValidationError({field: 'Select a valid profile.'})
        if profile.user.role != role:
            raise ValidationError({field: 'The profile must have the matching account role.'})


def check_enrollment(student_id, course_id, term_id):
    if student_id and course_id and term_id:
        if not Enrollment.objects.filter(student_id=student_id, course_id=course_id, term_id=term_id).exclude(status=Enrollment.Status.WITHDRAWN).exists():
            raise ValidationError({'student': 'The student must be enrolled in this course and term.'})


def check_updater(user, course_id, term_id):
    if not user.is_active:
        raise ValidationError({'updated_by': 'The updater must have an active account.'})
    if user.role == User.Role.ADMINISTRATOR:
        return
    if user.role == User.Role.TEACHER and TeachingAssignment.objects.filter(teacher__user=user, course_id=course_id, term_id=term_id).exists():
        return
    raise ValidationError({'updated_by': 'The updater must be an administrator or assigned teacher.'})


class TeachingAssignment(ValidatedModel):
    teacher = models.ForeignKey('accounts.TeacherProfile', on_delete=models.PROTECT, related_name='teaching_assignments')
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='teaching_assignments')
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name='teaching_assignments')
    section = models.CharField(max_length=50, blank=True, default='')

    class Meta:
        ordering = ('term__start_date', 'course__code', 'section')
        constraints = [models.UniqueConstraint(fields=('teacher', 'course', 'term', 'section'), name='academics_unique_assignment')]

    def clean(self):
        super().clean()
        self.section = self.section.strip()
        check_profile(self, 'teacher', User.Role.TEACHER)

    def __str__(self):
        return f'{self.teacher} — {self.course} ({self.term})'


class Enrollment(ValidatedModel):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'
        WITHDRAWN = 'withdrawn', 'Withdrawn'

    student = models.ForeignKey('accounts.StudentProfile', on_delete=models.PROTECT, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='enrollments')
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name='enrollments')
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.ACTIVE)
    enrollment_date = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ('term__start_date', 'course__code', 'student__student_number')
        constraints = [
            models.UniqueConstraint(fields=('student', 'course', 'term'), name='academics_unique_enrollment'),
            models.CheckConstraint(condition=models.Q(status__in=['active', 'completed', 'withdrawn']), name='academics_valid_enrollment_status'),
        ]

    def clean(self):
        super().clean()
        check_profile(self, 'student', User.Role.STUDENT)

    def __str__(self):
        return f'{self.student} — {self.course} ({self.term})'


class Assessment(ValidatedModel):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='assessments')
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name='assessments')
    title = models.CharField(max_length=150)
    category = models.CharField(max_length=50, blank=True)
    maximum_score = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'), validators=[MinValueValidator(0), MaxValueValidator(100)])
    due_date = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ('term__start_date', 'course__code', 'title')
        constraints = [
            models.CheckConstraint(condition=models.Q(maximum_score__gt=0), name='academics_positive_maximum_score'),
            models.CheckConstraint(condition=models.Q(weight__gte=0, weight__lte=100), name='academics_valid_assessment_weight'),
        ]

    def clean(self):
        super().clean()
        if self.pk and not self._state.adding:
            if finite_decimal(self.maximum_score) is not None and self.scores.filter(value__gt=self.maximum_score).exists():
                raise ValidationError({'maximum_score': 'Maximum score cannot be below an existing score.'})
            original = Assessment.objects.get(pk=self.pk)
            if self.scores.exists() and (original.course_id != self.course_id or original.term_id != self.term_id):
                raise ValidationError('An assessment with scores cannot change course or term.')

    def __str__(self):
        return f'{self.course.code} — {self.title}'


class Score(ValidatedModel):
    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, related_name='scores')
    student = models.ForeignKey('accounts.StudentProfile', on_delete=models.PROTECT, related_name='scores')
    value = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    resit_value = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    resit_policy_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    resit_effective_value = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, editable=False)
    remarks = models.TextField(blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='updated_scores', editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('assessment__course__code', 'assessment__title', 'student__student_number')
        constraints = [
            models.UniqueConstraint(fields=('assessment', 'student'), name='academics_unique_student_score'),
            models.CheckConstraint(condition=models.Q(value__gte=0), name='academics_nonnegative_score'),
            models.CheckConstraint(condition=models.Q(resit_value__isnull=True, resit_effective_value__isnull=True) | models.Q(resit_value__gte=0, resit_effective_value__gte=0), name='academics_valid_resit_values'),
        ]

    def clean(self):
        super().clean()
        check_profile(self, 'student', User.Role.STUDENT)
        if self.assessment_id:
            assessment = related(self, 'assessment')
            if finite_decimal(self.value) is not None and finite_decimal(self.value) > assessment.maximum_score:
                raise ValidationError({'value': 'Score must not exceed the assessment maximum.'})
            check_enrollment(self.student_id, assessment.course_id, assessment.term_id)
            if self.updated_by_id:
                check_updater(related(self, 'updated_by'), assessment.course_id, assessment.term_id)
            from .grading import validate_score_resit
            validate_score_resit(self)

    @property
    def effective_value(self):
        return self.resit_effective_value if self.resit_value is not None else self.value

    @property
    def effective_percentage(self):
        return self.effective_value * 100 / self.effective_maximum

    @property
    def effective_maximum(self):
        return Decimal(self.resit_policy_snapshot['maximum_score']) if self.resit_value is not None else self.assessment.maximum_score

    @property
    def course_resit_required(self):
        return self.resit_value is not None and self.effective_percentage < Decimal(self.resit_policy_snapshot['pass_percentage'])

    @property
    def is_course_resit_required(self):
        return self.course_resit_required

    @property
    def can_resit(self):
        from .grading import eligible_for_resit
        return self.resit_value is None and eligible_for_resit(self)

    @property
    def outcome(self):
        from .grading import policy_for
        if self.resit_value is not None:
            threshold = Decimal(self.resit_policy_snapshot['pass_percentage'])
            return 'Pass · resit' if self.effective_percentage >= threshold else 'Fail — course resit required'
        policy = policy_for(self)
        if policy is None:
            return 'No grading rule configured'
        return 'Pass' if self.effective_percentage >= policy.pass_percentage else 'Resit required'

    def __str__(self):
        return f'{self.student} — {self.assessment}: {self.value}'


class AttendanceSession(ValidatedModel):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='attendance_sessions')
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name='attendance_sessions')
    teacher = models.ForeignKey('accounts.TeacherProfile', on_delete=models.PROTECT, related_name='attendance_sessions')
    date = models.DateField()
    lesson_label = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        ordering = ('-date', 'course__code', 'lesson_label')
        constraints = [models.UniqueConstraint(fields=('course', 'term', 'date', 'lesson_label'), name='academics_unique_attendance_session')]

    def clean(self):
        super().clean()
        self.lesson_label = self.lesson_label.strip()
        check_profile(self, 'teacher', User.Role.TEACHER)
        if self.term_id and self.date and not related(self, 'term').start_date <= self.date <= related(self, 'term').end_date:
            raise ValidationError({'date': 'Session date must fall within its term.'})
        if self.teacher_id and self.course_id and self.term_id:
            if not TeachingAssignment.objects.filter(teacher_id=self.teacher_id, course_id=self.course_id, term_id=self.term_id).exists():
                raise ValidationError({'teacher': 'The teacher must be assigned to this course and term.'})
        if self.pk and not self._state.adding and self.records.exists():
            original = AttendanceSession.objects.get(pk=self.pk)
            if original.course_id != self.course_id or original.term_id != self.term_id:
                raise ValidationError('A session with records cannot change course or term.')

    def __str__(self):
        return f'{self.course.code} — {self.date} {self.lesson_label}'.strip()


class AttendanceRecord(ValidatedModel):
    class Status(models.TextChoices):
        PRESENT = 'present', 'Present'
        ABSENT = 'absent', 'Absent'
        LATE = 'late', 'Late'
        EXCUSED = 'excused', 'Excused'

    session = models.ForeignKey(AttendanceSession, on_delete=models.PROTECT, related_name='records')
    student = models.ForeignKey('accounts.StudentProfile', on_delete=models.PROTECT, related_name='attendance_records')
    status = models.CharField(max_length=7, choices=Status.choices)
    remarks = models.TextField(blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='updated_attendance_records', editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-session__date', 'student__student_number')
        constraints = [
            models.UniqueConstraint(fields=('session', 'student'), name='academics_unique_attendance_record'),
            models.CheckConstraint(condition=models.Q(status__in=['present', 'absent', 'late', 'excused']), name='academics_valid_attendance_status'),
        ]

    def clean(self):
        super().clean()
        check_profile(self, 'student', User.Role.STUDENT)
        if self.session_id:
            session = related(self, 'session')
            check_enrollment(self.student_id, session.course_id, session.term_id)
            if self.updated_by_id:
                check_updater(related(self, 'updated_by'), session.course_id, session.term_id)

    def __str__(self):
        return f'{self.student} — {self.session}: {self.get_status_display()}'


from .grading_models import CourseTermGradingPolicy  # noqa: E402,F401

from .correction_models import AcademicCorrection  # noqa: E402,F401
