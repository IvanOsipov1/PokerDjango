import random
import uuid

from channels.db import database_sync_to_async
from django.db import models
import asyncio
from django.utils import timezone
from django.apps import apps
from asgiref.sync import sync_to_async


def get_room_player_model():
    return apps.get_model('rooms', 'RoomPlayer')


class Room(models.Model):
    name = models.CharField(max_length=255, default="Новая комната")
    max_players = models.PositiveIntegerField(default=10)
    big_blind = models.PositiveIntegerField(default=50, verbose_name="Большой блайнд")  # Значение по умолчанию
    unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_active = models.BooleanField(default=False)
    pot = models.FloatField(default=0.0, verbose_name="Текущий банк")  # Общий банк
    check_count = models.PositiveIntegerField(default=0, verbose_name="Количество чеков")  # Счётчик чеков
    current_bet = models.PositiveIntegerField(default=0,
                                        verbose_name="Текущая максимальная ставка")  # Максимальная ставка
    current_player = models.PositiveIntegerField(null=True, blank=True, verbose_name="Текущий игрок")
    flag_is_started = models.BooleanField(default=False)
    def __str__(self):
        return f"Room {self.name} - ID: {self.unique_id}"

