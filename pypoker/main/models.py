import random
import uuid
from django.db import models
import asyncio
from django.utils import timezone
from django.apps import apps


def get_room_player_model():
    return apps.get_model('rooms', 'RoomPlayer')

class Room(models.Model):
    name = models.CharField(max_length=255, default="Новая комната")
    max_players = models.PositiveIntegerField(default=10)
    blinds = models.CharField(max_length=20)
    unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return f"Room {self.name} - ID: {self.unique_id}"

    def assign_heads_up_positions(self):
        roomplayer_set = get_room_player_model()
        """Назначает роли для Heads-Up игры (2 игрока)."""
        # Получаем активных игроков за столом
        active_players = list(self.roomplayer_set.filter(is_active=True))

        if len(active_players) < 2:
            self.is_active = False
            self.save()
            print('Недостаточно игроков для Heads-Up')
            return

        # Сбрасываем текущие роли
        for player in active_players:
            player.role = 'Player'
            player.save()

        # Случайно выбираем диллера
        dealer_index = random.randint(0, 1)
        big_blind_index = 1 - dealer_index

        active_players[dealer_index].role = 'Dealer'
        active_players[dealer_index].save()

        active_players[big_blind_index].role = 'Big Blind'
        active_players[big_blind_index].save()

        print(f"Диллер: {active_players[dealer_index].user.username}")
        print(f"Big Blind: {active_players[big_blind_index].user.username}")
     async def start_game(self):
            """Запускает игру с 3-секундной задержкой после подключения игрока."""
            print("Ожидание других игроков... Игра начнется через 3 секунды.")
            await asyncio.sleep(3)  # 3-секундная задержка

            # Получаем всех активных игроков
            active_players = list(self.roomplayer_set.filter(is_active=True))

            if len(active_players) < 2:
                print("Недостаточно игроков для старта игры.")
                return

            # Назначаем позиции (диллер, биг блайнд и т.д.)
            self.assign_positions()
            self.is_active = True
            self.save()

            # Отправляем сообщение клиентам о начале игры через WebSocket
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            await channel_layer.group_send(
                f"room_{self.unique_id}",
                {
                    "type": "game.start",
                    "message": "Игра началась!",
                }
            )