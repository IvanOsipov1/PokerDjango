from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static



urlpatterns = [
    path('<uuid:unique_id>/', views.room_detail, name='room_detail'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)