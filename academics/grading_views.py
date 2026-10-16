from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User
from accounts.policies import roles_required
from .models import CourseTermGradingPolicy


class GradingPolicyForm(forms.ModelForm):
    class Meta:
        model = CourseTermGradingPolicy
        fields = ('course', 'term', 'enabled', 'pass_percentage', 'method', 'resit_weight', 'cap_percentage')


@roles_required(User.Role.ADMINISTRATOR)
def grading_policies(request, pk=None):
    instance = get_object_or_404(CourseTermGradingPolicy, pk=pk) if pk is not None else None
    form = GradingPolicyForm(request.POST if request.method == 'POST' else None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Course and term grading rule saved. Existing resit results keep their recorded calculation.')
        return redirect('academics:grading_policies')
    return render(request, 'academics/grading_policies.html', {
        'form': form, 'editing': instance,
        'policies': CourseTermGradingPolicy.objects.select_related('course', 'term__academic_year'),
    })
