from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView
app_name = "users"

urlpatterns = [
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('register/', views.register, name='register'),
]