from django import forms
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render, redirect

from accounts.models import StudentProfile, User
from accounts.policies import roles_required, visible_students, visible_scores, visible_attendance, visible_enrollments
from academics.grading import attach_course_resit_warnings


class StudentSearchForm(forms.Form):
    q = forms.CharField(required=False, max_length=100, label='Student number or name', strip=True)


@roles_required(User.Role.ADMINISTRATOR, User.Role.TEACHER)
def student_list(request):
    form = StudentSearchForm(request.GET)
    queryset = visible_students(request.user).order_by('student_number')
    query = ''
    if form.is_valid():
        query = form.cleaned_data['q']
        if query:
            queryset = queryset.filter(Q(student_number__istartswith=query) | Q(user__first_name__istartswith=query) | Q(user__last_name__istartswith=query))
    else:
        queryset = queryset.none()
    page = Paginator(queryset, 20).get_page(request.GET.get('page'))
    return render(request, 'students/list.html', {'form': form, 'page_obj': page, 'query': query})


@roles_required(*User.Role.values)
def student_detail(request, pk):
    get_object_or_404(StudentProfile.objects.only('pk'), pk=pk)
    profile = visible_students(request.user).filter(pk=pk).first()
    if profile is None:
        raise PermissionDenied
    enrollments = visible_enrollments(request.user).filter(student=profile)
    scores = visible_scores(request.user).filter(student=profile)
    attendance = visible_attendance(request.user).filter(student=profile)
    return render(request, 'students/detail.html', {'profile': profile,
        'profile_counts': [('Enrolled courses', enrollments.exclude(status='withdrawn').values('course_id').distinct().count()),
            ('Assessment records', scores.count()), ('Attendance records', attendance.count()),
            ('Present records', attendance.filter(status='present').count())],
        'enrollments': attach_course_resit_warnings(enrollments.order_by('-term__start_date', 'course__code')[:8], scores),
        'records': scores.order_by('assessment__term__start_date', 'assessment__course__code', 'assessment__title')[:12]})


@roles_required(User.Role.STUDENT)
def my_profile(request):
    profile = get_object_or_404(visible_students(request.user), user=request.user)
    return redirect('students:detail', pk=profile.pk)
