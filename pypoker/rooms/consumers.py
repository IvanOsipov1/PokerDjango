import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.apps import apps
from asgiref.sync import sync_to_async
from django.db import transaction


def get_room_model():
    return apps.get_model('main', 'Room')


def get_room_player_model():
    return apps.get_model('rooms', 'RoomPlayer')


class RoomConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['unique_id']
        self.room_group_name = f"room_{self.room_id}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        # Получаем текущих игроков для комнаты
        RoomPlayer = get_room_player_model()
        players = await sync_to_async(list)(
            RoomPlayer.objects.filter(room__unique_id=self.room_id).values(
                'user__username', 'seat_number', 'stack', 'role'
            )
        )
        for player in players:
            player['stack'] = float(player['stack'])

        # Отправляем информацию о текущих игроках клиенту
        await self.send(text_data=json.dumps({
            'action': 'load_players',
            'players': players
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')

        if action == 'sit':
            seat_number = data.get('seat')
            stack = data.get('stack')
            user = self.scope["user"]

            if user.is_authenticated:
                Room = get_room_model()
                room = await Room.objects.aget(unique_id=self.room_id)

                # Проверка, что игрок уже сидит за каким-либо местом в этой комнате
                if await self.player_already_in_room(room, user):
                    await self.send(text_data=json.dumps({
                        'action': 'error',
                        'message': 'You are already seated at this table!'
                    }))
                    return

                if not await self.seat_taken(room, seat_number):
                    # Присваиваем роль игроку
                    role = await self.assign_role(room)

                    # Создаем игрока
                    await self.create_player(user, room, seat_number, stack, role)

                    # Отправляем событие другим игрокам
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'player_join',
                            'username': user.username,
                            'seat': seat_number,
                            'stack': stack,
                            'role': role
                        }
                    )

    async def player_join(self, event):
        await self.send(text_data=json.dumps({
            'action': 'player_join',
            'username': event['username'],
            'seat': event['seat'],
            'stack': event['stack'],
            'role': event['role'],
        }))

    async def game_start(self, event):
        message = event['message']
        await self.send(text_data=json.dumps({
            'action': 'game_start',
            'message': message,
        }))

    @staticmethod
    async def seat_taken(room, seat_number):
        RoomPlayer = get_room_player_model()
        return await RoomPlayer.objects.filter(room=room, seat_number=seat_number).aexists()

    @staticmethod
    async def player_already_in_room(room, user):
        RoomPlayer = get_room_player_model()
        return await RoomPlayer.objects.filter(room=room, user=user).aexists()

    async def create_player(self, user, room, seat_number, stack, role):
        RoomPlayer = get_room_player_model()

        def create_player_sync():
            with transaction.atomic():
                # Проверка наличия игрока в комнате перед созданием
                if RoomPlayer.objects.filter(room=room, user=user).exists():
                    return {'error': 'You are already seated at this table!'}

                # Проверка занятости места
                if RoomPlayer.objects.filter(room=room, seat_number=seat_number).exists():
                    return {'error': 'This seat is already taken!'}

                # Создание игрока
                RoomPlayer.objects.create(
                    user=user,
                    room=room,
                    seat_number=seat_number,
                    stack=stack,
                    role=role
                )

        result = await sync_to_async(create_player_sync)()

        if result and 'error' in result:
            await self.send(text_data=json.dumps({
                'action': 'error',
                'message': result['error']
            }))

    async def assign_role(self, room):
        """
        Логика для назначения роли игроку, например BB, SB и т.д.
        """
        RoomPlayer = get_room_player_model()
        existing_roles = await sync_to_async(list)(
            RoomPlayer.objects.filter(room=room).values_list('role', flat=True)
        )
        roles = ['BB', 'SB', 'Dealer']
        for role in roles:
            if role not in existing_roles:
                return role
        return None  # Если все роли заняты

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')
        amount = data.get('amount', 0)
        user = self.scope["user"]

        if action in ['fold', 'call', 'check', 'raise'] and user.is_authenticated:
            await self.process_betting_action(action, user, amount)

    async def process_betting_action(self, action, user, amount):
        # Ищем текущую комнату и игрока
        Room = get_room_model()
        RoomPlayer = get_room_player_model()
        room = await Room.objects.aget(unique_id=self.room_id)
        player = await RoomPlayer.objects.aget(room=room, user=user)

        # Логика действий игрока
        if action == 'fold':
            player.fold()
        elif action == 'call':
            call_amount = room.current_bet - player.current_bet
            room.pot += player.call(call_amount)
        elif action == 'check':
            player.check()
        elif action == 'raise':
            if amount >= room.current_bet * 2 and amount <= player._cash:
                room.pot += player.raise_bet(amount)

        # Сохраняем изменения и уведомляем игроков
        await sync_to_async(player.save)()
        await sync_to_async(room.save)()
        await self.broadcast_game_update(room)

    async def broadcast_game_update(self, room):
        RoomPlayer = get_room_player_model()
        players = await sync_to_async(list)(RoomPlayer.objects.filter(room=room))

        game_state = {
            "action": "update_game",
            "pot": room.pot,
            "current_bet": room.current_bet,
            "players": [
                {
                    "username": player.user.username,
                    "cash": player._cash,
                    "current_bet": player.current_bet,
                    "active_in_round": player.active_in_round
                } for player in players
            ]
        }

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_update',
                'message': game_state
            }
        )

    async def game_update(self, event):
        await self.send(text_data=json.dumps(event['message']))