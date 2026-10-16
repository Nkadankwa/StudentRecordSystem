from django.urls import reverse
from django.utils import timezone
from academics.models import Term
from .models import User
from .policies import visible_assignments, visible_enrollments


def workspace(request):
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}
    terms = Term.objects.select_related('academic_year')
    if user.role == User.Role.TEACHER:
        terms = terms.filter(pk__in=visible_assignments(user).values('term_id'))
    elif user.role == User.Role.STUDENT:
        terms = terms.filter(pk__in=visible_enrollments(user).values('term_id'))
    today = timezone.localdate()
    period = terms.filter(start_date__lte=today, end_date__gte=today).order_by('-start_date').first()
    if period is None:
        period = terms.order_by('-start_date').first()
    route = request.resolver_match.url_name if request.resolver_match else ''
    links = [('Dashboard', f'accounts:{user.role}_home', 'dashboard', route.endswith('_home'))]
    if user.role == 'student':
        links.append(('My profile', 'students:me', 'students', route in {'me', 'detail', 'record'}))
    else:
        links += [('My students' if user.role == 'teacher' else 'Students directory', 'students:list', 'students', route in {'list', 'detail', 'record'}),
                  ('My classes' if user.role == 'teacher' else 'Teaching assignments', 'academics:assignments', 'courses', route in {'assignments', 'roster'})]
    links += [('My scores' if user.role == 'student' else 'Assessments & scores', 'academics:scores', 'scores', route in {'scores', 'score_entry'}),
              ('My attendance' if user.role == 'student' else 'Attendance sessions', 'academics:attendance', 'attendance', route in {'attendance', 'attendance_entry', 'attendance_new'})]
    if user.role == 'administrator':
        links += [('Courses & terms', 'academics:catalog', 'courses', route == 'catalog'),
                  ('Grading rules', 'academics:grading_policies', 'scores', route in {'grading_policies', 'grading_policy_edit'}),
                  ('Setup & administration', 'accounts:setup', 'settings', route == 'setup')]
    if user.role in {'administrator', 'teacher'}:
        from academics.models import AcademicCorrection
        if user.role == 'administrator':
            pending = AcademicCorrection.objects.filter(status='pending').count()
            label = f'Record changes ({pending})' if pending else 'Record changes'
        else:
            label = 'My corrections'
        links.append((label, 'academics:corrections', 'attendance', route in {'corrections', 'correction_detail'}))
    names = (user.get_full_name() or user.username).split()
    from .layouts import allowed_widgets
    from .models import WorkspaceLayout
    layout = None
    if allowed_widgets(user, route) is not None:
        preferences = WorkspaceLayout.objects.filter(user=user, page=route).values_list('preferences', flat=True).first() or {}
        layout = {'page': route, 'hidden': preferences.get('hidden', []), 'collapsed': preferences.get('collapsed', [])}
    shortcuts = []
    if user.role == User.Role.ADMINISTRATOR and user.is_staff:
        for app, model, label, icon in [('accounts', 'user', 'Add user / profile', 'students'),
                ('academics', 'course', 'Add course', 'courses'), ('academics', 'term', 'Add term', 'calendar')]:
            if user.has_perm(f'{app}.add_{model}'):
                shortcuts.append({'url': reverse(f'admin:{app}_{model}_add'), 'label': label, 'icon': icon})
        if user.has_perm('auth.view_group') or user.has_perm('auth.change_group'):
            shortcuts.append({'url': reverse('admin:auth_group_changelist'), 'label': 'Manage permissions', 'icon': 'settings'})
    return {'workspace_period': period,
        'workspace_layout': layout,
        'workspace_admin_shortcuts': shortcuts,
        'workspace_initials': ''.join(part[0] for part in names[:2]).upper(),
        'workspace_nav': [{'label': label, 'url': reverse(url), 'icon': icon, 'active': active}
                          for label, url, icon, active in links]}
