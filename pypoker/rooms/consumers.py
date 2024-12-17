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
                'user__username', 'seat_number', 'stack'
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
                    await self.create_player(user, room, seat_number, stack)

                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'player_join',
                            'username': user.username,
                            'seat': seat_number,
                            'stack': stack,
                        }
                    )

    async def player_join(self, event):
        await self.send(text_data=json.dumps({
            'action': 'player_join',
            'username': event['username'],
            'seat': event['seat'],
            'stack': event['stack'],
        }))

    @staticmethod
    async def seat_taken(room, seat_number):
        RoomPlayer = get_room_player_model()
        return await RoomPlayer.objects.filter(room=room, seat_number=seat_number).aexists()

    @staticmethod
    async def player_already_in_room(room, user):
        RoomPlayer = get_room_player_model()
        return await RoomPlayer.objects.filter(room=room, user=user).aexists()

    async def create_player(self, user, room, seat_number, stack):
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
                    stack=stack
                )

        result = await sync_to_async(create_player_sync)()

        if result and 'error' in result:
            await self.send(text_data=json.dumps({
                'action': 'error',
                'message': result['error']
            }))
