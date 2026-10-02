from django.urls import path
from . import views

app_name = 'students'
urlpatterns = [
    path('', views.student_list, name='list'),
    path('me/', views.my_profile, name='me'),
    path('<int:pk>/', views.student_detail, name='detail'),
]
