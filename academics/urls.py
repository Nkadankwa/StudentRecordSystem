from django.urls import path
from . import views, grading_views

app_name = 'academics'
urlpatterns = [
    path('corrections/', views.correction_list, name='corrections'),
    path('corrections/<int:pk>/', views.correction_detail, name='correction_detail'),
    path('grading/', grading_views.grading_policies, name='grading_policies'),
    path('grading/<int:pk>/', grading_views.grading_policies, name='grading_policy_edit'),
    path('assignments/', views.assignments, name='assignments'),
    path('assignments/<int:pk>/roster/', views.assignment_roster, name='roster'),
    path('catalog/', views.catalog, name='catalog'),
    path('scores/', views.scores, name='scores'),
    path('scores/<int:pk>/entry/', views.score_entry, name='score_entry'),
    path('attendance/', views.attendance, name='attendance'),
    path('attendance/new/', views.attendance_entry, name='attendance_new'),
    path('attendance/<int:pk>/entry/', views.attendance_entry, name='attendance_entry'),
    path('records/<int:pk>/', views.student_record, name='record'),
]
