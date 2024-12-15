import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import rooms.routing  # Подключаем маршруты из приложения


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project_name.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),  # HTTP запросы обрабатываются как обычно
    "websocket": AuthMiddlewareStack(  # Добавляем поддержку WebSocket
        URLRouter(
            rooms.routing.websocket_urlpatterns
        )
    ),
})
