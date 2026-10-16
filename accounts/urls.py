from django.urls import path

from .models import User
from .views import AccountLoginView, AccountLogoutView, home, role_home, setup, save_layout

app_name = 'accounts'
urlpatterns = [
    path('layout/', save_layout, name='save_layout'),
    path('setup/', setup, name='setup'),
    path('login/', AccountLoginView.as_view(), name='login'),
    path('logout/', AccountLogoutView.as_view(), name='logout'),
    path('home/', home, name='home'),
    path('home/student/', role_home, {'role': User.Role.STUDENT}, name='student_home'),
    path('home/teacher/', role_home, {'role': User.Role.TEACHER}, name='teacher_home'),
    path('home/administrator/', role_home, {'role': User.Role.ADMINISTRATOR}, name='administrator_home'),
]
