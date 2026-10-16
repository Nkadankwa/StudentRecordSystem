from django.conf import settings
from django.db import models


class AcademicCorrection(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Awaiting review'
        ACCEPTED = 'accepted', 'Accepted'
        REVOKED = 'revoked', 'Revoked'

    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='academic_corrections')
    kind = models.CharField(max_length=10, choices=[('scores', 'Scores'), ('attendance', 'Attendance')])
    assessment = models.ForeignKey('academics.Assessment', null=True, blank=True, on_delete=models.PROTECT)
    session = models.ForeignKey('academics.AttendanceSession', null=True, blank=True, on_delete=models.PROTECT)
    reason = models.TextField()
    changes = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='reviewed_corrections')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_reason = models.TextField(blank=True)

    class Meta:
        ordering = ('-created_at', '-pk')

    def __str__(self):
        return f'{self.get_kind_display()} correction by {self.teacher} — {self.get_status_display()}'
