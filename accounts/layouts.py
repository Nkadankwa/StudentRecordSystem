"""Only these presentation sections may be personalized, separately per user/page."""
LAYOUTS = {
    'administrator_home': ('administrator', ['enrolled', 'faculty', 'assessment-total', 'attendance-total', 'directory', 'quick-setup', 'recent-assessments', 'corrections']),
    'teacher_home': ('teacher', ['metric-1', 'metric-2', 'metric-3', 'metric-4', 'assignments', 'score-entry', 'assigned-students']),
    'student_home': ('student', ['metric-1', 'metric-2', 'metric-3', 'latest-scores', 'recent-attendance', 'my-courses']),
    'detail': (None, ['metric-1', 'metric-2', 'metric-3', 'metric-4', 'enrolments', 'profile-scores']),
    'catalog': ('administrator', ['catalog-courses', 'catalog-terms']),
    'setup': ('administrator', ['setup-permissions', 'setup-order']),
}


def allowed_widgets(user, page):
    entry = LAYOUTS.get(page)
    if entry is None or (entry[0] and user.role != entry[0]):
        return None
    return entry[1]
