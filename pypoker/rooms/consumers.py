import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.apps import apps



def get_room_model():
    return apps.get_model('main', 'Room')

def get_room_player_model():
    return apps.get_model('rooms', 'RoomPlayer')


class RoomConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f"room_{self.room_id}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

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
    async def create_player(user, room, seat_number, stack):
        RoomPlayer = get_room_player_model()
        await RoomPlayer.objects.acreate(
            user=user,
            room=room,
            seat_number=seat_number,
            balance_at_table=stack
        )
