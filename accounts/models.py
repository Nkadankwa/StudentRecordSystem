from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class AccountManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('role', User.Role.ADMINISTRATOR)
        if extra_fields['role'] != User.Role.ADMINISTRATOR:
            raise ValueError('A superuser must have the administrator role.')
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        TEACHER = 'teacher', 'Teacher'
        ADMINISTRATOR = 'administrator', 'Administrator'

    role = models.CharField(max_length=13, choices=Role.choices, default=Role.STUDENT)
    objects = AccountManager()

    class Meta(AbstractUser.Meta):
        indexes = [models.Index(fields=['first_name'], name='accounts_first_name_idx'),
                   models.Index(fields=['last_name'], name='accounts_last_name_idx')]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=['student', 'teacher', 'administrator']),
                name='accounts_user_valid_role',
            ),
            models.CheckConstraint(
                condition=models.Q(is_superuser=False) | models.Q(role='administrator'),
                name='accounts_superuser_administrator',
            ),
        ]

    def clean(self):
        super().clean()
        if self.is_superuser and self.role != self.Role.ADMINISTRATOR:
            raise ValidationError({'role': 'A superuser must be an administrator.'})
        if self.pk and not self._state.adding:
            for profile_model, role in (
                (StudentProfile, self.Role.STUDENT),
                (TeacherProfile, self.Role.TEACHER),
            ):
                if self.role != role and profile_model.objects.filter(user_id=self.pk).exists():
                    raise ValidationError({'role': 'Remove the existing profile before changing this role.'})


class StudentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_profile',
        limit_choices_to={'role': User.Role.STUDENT},
    )
    student_number = models.CharField(max_length=30, unique=True)
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=100, blank=True)

    def clean(self):
        super().clean()
        if self.user_id and self.user.role != User.Role.STUDENT:
            raise ValidationError({'user': 'Select a user with the student role.'})
        if self.date_of_birth and self.date_of_birth > timezone.localdate():
            raise ValidationError({'date_of_birth': 'Date of birth cannot be in the future.'})

    @property
    def age(self):
        today = timezone.localdate()
        born = self.date_of_birth
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    def __str__(self):
        return f'{self.student_number} — {self.user.get_full_name() or self.user.username}'


class TeacherProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='teacher_profile',
        limit_choices_to={'role': User.Role.TEACHER},
    )
    employee_number = models.CharField(max_length=30, unique=True)

    def clean(self):
        super().clean()
        if self.user_id and self.user.role != User.Role.TEACHER:
            raise ValidationError({'user': 'Select a user with the teacher role.'})

    def __str__(self):
        return f'{self.employee_number} — {self.user.get_full_name() or self.user.username}'


class WorkspaceLayout(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='workspace_layouts')
    page = models.CharField(max_length=32)
    preferences = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('user', 'page'), name='accounts_unique_workspace_layout')]
