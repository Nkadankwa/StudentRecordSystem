from django.urls import path
from . import views

app_name = 'academics'
urlpatterns = [
    path('scores/', views.scores, name='scores'),
    path('scores/<int:pk>/entry/', views.score_entry, name='score_entry'),
    path('attendance/', views.attendance, name='attendance'),
    path('attendance/new/', views.attendance_entry, name='attendance_new'),
    path('attendance/<int:pk>/entry/', views.attendance_entry, name='attendance_entry'),
    path('records/<int:pk>/', views.student_record, name='record'),
]
