from django import forms
from django.forms import formset_factory

from accounts.policies import visible_assignments
from .models import AttendanceRecord


class RecordFilterForm(forms.Form):
    course = forms.ModelChoiceField(queryset=None, required=False)
    term = forms.ModelChoiceField(queryset=None, required=False)

    def __init__(self, *args, records, relation, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Course, Term
        self.fields['course'].queryset = Course.objects.filter(pk__in=records.values(f'{relation}__course_id')).order_by('code')
        self.fields['term'].queryset = Term.objects.filter(pk__in=records.values(f'{relation}__term_id')).select_related('academic_year').order_by('-start_date')


class AccessibleEntryForm(forms.Form):
    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields and not self.fields[name].widget.is_hidden:
                self.fields[name].widget.attrs.update({'aria-invalid': 'true',
                    'aria-describedby': f'{self[name].auto_id}_errors'})


class ScoreRowForm(AccessibleEntryForm):
    student = forms.IntegerField(widget=forms.HiddenInput)
    value = forms.DecimalField(max_digits=8, decimal_places=2, min_value=0, required=False, label='Score')
    remarks = forms.CharField(required=False, max_length=2000, widget=forms.Textarea(attrs={'rows': 2}))


class AttendanceRowForm(AccessibleEntryForm):
    student = forms.IntegerField(widget=forms.HiddenInput)
    status = forms.ChoiceField(choices=[('', 'Choose status')] + list(AttendanceRecord.Status.choices))
    remarks = forms.CharField(required=False, max_length=2000, widget=forms.Textarea(attrs={'rows': 2}))


ScoreFormSet = formset_factory(ScoreRowForm, extra=0, max_num=1000, validate_max=True, absolute_max=1000)
AttendanceFormSet = formset_factory(AttendanceRowForm, extra=0, max_num=1000, validate_max=True, absolute_max=1000)


class AttendanceSessionForm(AccessibleEntryForm):
    assignment = forms.ModelChoiceField(queryset=None, label='Course, term and teacher')
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    lesson_label = forms.CharField(max_length=100, required=False)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assignment'].queryset = visible_assignments(user)
