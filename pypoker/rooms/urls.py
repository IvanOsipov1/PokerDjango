from django.urls import path
from . import views

urlpatterns = [
    path('<uuid:room_id>/', views.room_view, name='room_detail'),

]