from django.contrib import admin

from .models import (
    AcademicYear, Course, Term, Assessment, AttendanceRecord, AttendanceSession,
    Enrollment, Score, TeachingAssignment,
)


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ('name', 'academic_year', 'start_date', 'end_date')
    list_filter = ('academic_year',)
    search_fields = ('name', 'academic_year__name')
    list_select_related = ('academic_year',)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'title')


@admin.register(TeachingAssignment)
class TeachingAssignmentAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'course', 'term', 'section')
    list_filter = ('term', 'course')
    search_fields = ('teacher__employee_number', 'teacher__user__username', 'course__code', 'section')
    list_select_related = ('teacher__user', 'course', 'term__academic_year')


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'term', 'status', 'enrollment_date')
    list_filter = ('term', 'course', 'status')
    search_fields = ('student__student_number', 'student__user__username', 'course__code')
    list_select_related = ('student__user', 'course', 'term__academic_year')


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'term', 'maximum_score', 'weight', 'due_date')
    list_filter = ('course', 'term', 'category')
    search_fields = ('title', 'course__code')
    list_select_related = ('course', 'term__academic_year')


class AuditedAdmin(admin.ModelAdmin):
    readonly_fields = ('updated_by', 'created_at', 'updated_at')

    def get_form(self, request, obj=None, **kwargs):
        base_form = super().get_form(request, obj, **kwargs)

        class ActorForm(base_form):
            def __init__(self, *args, **form_kwargs):
                super().__init__(*args, **form_kwargs)
                self.instance.updated_by = request.user

        return ActorForm

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Score)
class ScoreAdmin(AuditedAdmin):
    list_display = ('student', 'assessment', 'value', 'updated_by', 'updated_at')
    list_filter = ('assessment__course', 'assessment__term')
    search_fields = ('student__student_number', 'assessment__title')
    list_select_related = ('student__user', 'assessment__course', 'updated_by')


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ('course', 'term', 'date', 'teacher', 'lesson_label')
    list_filter = ('course', 'term', 'teacher')
    search_fields = ('course__code', 'lesson_label', 'teacher__employee_number')
    date_hierarchy = 'date'
    list_select_related = ('course', 'term__academic_year', 'teacher__user')


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(AuditedAdmin):
    list_display = ('student', 'session', 'status', 'updated_by', 'updated_at')
    list_filter = ('status', 'session__course', 'session__term')
    search_fields = ('student__student_number', 'session__course__code')
    list_select_related = ('student__user', 'session__course', 'updated_by')
