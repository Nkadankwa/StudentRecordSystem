from decimal import Decimal

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from .models import ValidatedModel


class CourseTermGradingPolicy(ValidatedModel):
    class Method(models.TextChoices):
        REPLACE = 'replace', 'Use resit score'
        HIGHER = 'higher', 'Use higher of original and resit'
        WEIGHTED = 'weighted', 'Weighted original and resit'

    course = models.ForeignKey('academics.Course', on_delete=models.PROTECT, related_name='grading_policies')
    term = models.ForeignKey('academics.Term', on_delete=models.PROTECT, related_name='grading_policies')
    enabled = models.BooleanField(default=True)
    pass_percentage = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(100)])
    method = models.CharField(max_length=8, choices=Method.choices)
    resit_weight = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)], default=100, help_text='Percentage contributed by the resit when using the weighted calculation.')
    cap_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(100)], help_text='Optional maximum final percentage after a resit.')

    class Meta:
        ordering = ('course__code', '-term__start_date')
        constraints = [
            models.UniqueConstraint(fields=('course', 'term'), name='academics_unique_course_term_grading'),
            models.CheckConstraint(condition=models.Q(pass_percentage__gt=0, pass_percentage__lte=100), name='academics_valid_pass_percentage'),
            models.CheckConstraint(condition=models.Q(resit_weight__gte=0, resit_weight__lte=100), name='academics_valid_resit_weight'),
            models.CheckConstraint(condition=models.Q(cap_percentage__isnull=True) | models.Q(cap_percentage__gt=0, cap_percentage__lte=100), name='academics_valid_resit_cap'),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.cap_percentage is not None and self.pass_percentage is not None and self.cap_percentage < self.pass_percentage:
            raise ValidationError({'cap_percentage': 'The cap must allow a student to reach the pass threshold.'})

    def __str__(self):
        return f'{self.course.code} — {self.term}'
