from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView


urlpatterns = [
    path('', views.index, name='main'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('get_rooms', views.get_rooms, name='get_rooms')
    #path('create_room/', views.create_room, name='create_room'),
]