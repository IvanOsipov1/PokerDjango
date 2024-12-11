from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView


urlpatterns = [
    path('', views.menu, name='home'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('get_rooms', views.get_rooms, name='get_rooms'),
    path('index/', views.index),
    path('create_room', views.create_room, name='create_room'),
    path('rooms/<uuid:room_id>/', views.room_detail, name='room_detail'),
    #path('create_room/', views.create_room, name='create_room'),
]