from django.db import models
from users.models import CustomUser  # Импортируем CustomUser из приложения users
from main.models import Room  # Если ваша модель Room находится в другом файле (например, в app 'room')

class Player(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)  # Ссылка на CustomUser
    room = models.ForeignKey(Room, related_name='players', on_delete=models.CASCADE)  # Ссылка на комнату
    stack = models.DecimalField(max_digits=10, decimal_places=2)  # Баланс стека

    def __str__(self):
        return f'{self.user.username} in {self.room.name}'
