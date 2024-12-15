from django.urls import path
from . import views

urlpatterns = [
    path('<uuid:room_id>/', views.room_details, name='room_detail'),
]