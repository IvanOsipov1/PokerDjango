import json
from decimal import Decimal
import random
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.apps import apps
from asgiref.sync import sync_to_async
from django.db import transaction
from django.shortcuts import get_object_or_404


def get_room_model():
    return apps.get_model('main', 'Room')


def get_room_player_model():
    return apps.get_model('rooms', 'RoomPlayer')


class RoomConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['unique_id']
        self.room_group_name = f"room_{self.room_id}"

        Room = get_room_model()
        self.room = await sync_to_async(lambda: get_object_or_404(Room, unique_id=self.room_id))()

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        # Получаем текущих игроков для комнаты
        RoomPlayer = get_room_player_model()
        self.active_players = await sync_to_async(list)(
            RoomPlayer.objects.filter(room__unique_id=self.room_id).values(
                'user__username', 'seat_number', 'stack', 'role', 'is_active'
            )
        )

        # Преобразуем Decimal в float для stack
        for player in self.active_players:
            player['stack'] = float(player['stack'])

        # Восстанавливаем активного игрока, если он переподключается
        user = self.scope['user']
        current_player = await sync_to_async(
            lambda: RoomPlayer.objects.filter(room=self.room, user=user).first()
        )()

        if current_player:
            current_player.is_active = True
            await sync_to_async(current_player.save)()
            print(f"{user.username} переподключился")

        # Отправляем информацию о текущих игроках клиенту
        await self.send(text_data=json.dumps({
            'action': 'load_players',
            'players': self.active_players
        }))

        # Убедимся, что игра начнется только один раз
        if len(self.active_players) > 1 and not self.room.flag_is_started:
            print('БОЛЬШЕ 1')
            await self.start_game()
            self.room.flag_is_started = True
            await sync_to_async(self.room.save)()

        # Если игроков меньше двух, сбрасываем флаг игры
        if len(self.active_players) < 2:
            print('МЕНЬШЕ 2')
            self.room.flag_is_started = False
            await sync_to_async(self.room.save)()

    async def disconnect(self, close_code):
        user = self.scope['user']

        # Удаляем из группы канала при отключении
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

        # Обновляем статус игрока
        RoomPlayer = get_room_player_model()
        player = await sync_to_async(
            lambda: RoomPlayer.objects.filter(room=self.room, user=user).first()
        )()

        if player:
            player.is_active = False
            await sync_to_async(player.save)()
            print(f"{user.username} отключился")

        # Проверяем, осталось ли меньше двух активных игроков
        active_players_count = await sync_to_async(
            lambda: RoomPlayer.objects.filter(room=self.room, is_active=True).count()
        )()

        if active_players_count < 2 and self.room.flag_is_started:
            print('МЕНЬШЕ 2: Останавливаем игру')
            self.room.flag_is_started = False
            await sync_to_async(self.room.save)()

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')
        amount = data.get('amount', 0)
        user = self.scope["user"]

        if action in ['fold', 'call', 'check', 'raise'] and user.is_authenticated:
            await self.process_betting_action(action, user, amount)

        elif action == 'sit':
            RoomPlayer = get_room_player_model()
            seat_number = data.get('seat')
            stack = data.get('stack')

            if user.is_authenticated:
                await self.handle_sit_action(user, seat_number, stack)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'player_join',
                    'seat': data['seat'],
                    'username': self.scope["user"].username,
                    'stack': float(data['stack']),
                    'role': 'player'
                }
            )

            # Проверяем, если за столом больше одного игрока, запускаем игру
            players = await sync_to_async(
                lambda: list(RoomPlayer.objects.filter(room=self.room, is_active=1).order_by('seat_number')))()
            if len(players) > 1:
                await self.send(text_data=json.dumps({"message": "Игра начинается!"}))
            else:
                await self.send(text_data=json.dumps({"message": "Недостаточно игроков!"}))

    async def handle_sit_action(self, user, seat_number, stack):
        """
        Обрабатывает действия игрока при посадке за стол.
        """
        Room = get_room_model()
        room = await sync_to_async(lambda: Room.objects.get(unique_id=self.room_id))()

        # Проверяем, что игрок уже не сидит за столом
        if await self.player_already_in_room(room, user):
            await self.send(text_data=json.dumps({
                'action': 'error',
                'message': 'You are already seated at this table!'
            }))
            return

        # Проверяем, что место не занято
        if not await self.seat_taken(room, seat_number):
            # Добавляем игрока
            await self.create_player(user, room, seat_number, stack, role='Player')

            # Уведомляем других игроков о новом игроке
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'player_join',
                    'username': user.username,
                    'seat': seat_number,
                    'stack': stack,
                    'role': 'Player'
                }
            )

            # Назначаем роли, если за столом 2 или больше игроков
            await self.assign_positions(room)

    async def assign_positions(self, room):
        """
        Назначает роли игрокам за столом. Роли не изменяются, если игра уже начата.
        """
        if room.flag_is_started:
            print("Игра уже начата. Роли не переназначаются.")
            return

        RoomPlayer = get_room_player_model()

        # Получаем активных игроков
        self.active_players = await sync_to_async(list)(
            RoomPlayer.objects.filter(room=room, is_active=True).order_by('seat_number')
        )

        # Если игроков меньше двух, сбрасываем роли
        if len(self.active_players) < 2:
            for player in self.active_players:
                player.role = 'Player'
                await sync_to_async(player.save)()
            return

        # Сбрасываем роли всех игроков
        for player in self.active_players:
            player.role = 'Player'
            await sync_to_async(player.save)()

        if len(self.active_players) == 2:
            # Heads-Up: один Big Blind, другой Dealer
            dealer_index = random.randint(0, 1)
            big_blind_index = 1 - dealer_index

            self.active_players[dealer_index].role = 'Dealer'
            self.active_players[big_blind_index].role = 'Big Blind'

            await sync_to_async(self.active_players[dealer_index].save)()
            await sync_to_async(self.active_players[big_blind_index].save)()

        else:
            # Три и более игроков
            dealer_index = random.randint(0, len(self.active_players) - 1)
            small_blind_index = (dealer_index + 1) % len(self.active_players)
            big_blind_index = (dealer_index + 2) % len(self.active_players)

            self.active_players[dealer_index].role = 'Dealer'
            self.active_players[small_blind_index].role = 'Small Blind'
            self.active_players[big_blind_index].role = 'Big Blind'

            await sync_to_async(self.active_players[dealer_index].save)()
            await sync_to_async(self.active_players[small_blind_index].save)()
            await sync_to_async(self.active_players[big_blind_index].save)()

        print("Роли назначены.")

    async def process_betting_action(self, action, user, amount):
        Room = get_room_model()
        RoomPlayer = get_room_player_model()

        room = await Room.objects.aget(unique_id=self.room_id)
        player = await RoomPlayer.objects.aget(room=room, user=user)

        if action == 'fold':
            player.fold()
        elif action == 'call':
            call_amount = room.current_bet - player.current_bet
            room.pot += player.call(call_amount)
        elif action == 'check':
            player.check()
        elif action == 'raise':
            if amount >= room.current_bet * 2 and amount <= player.stack:
                room.pot += player.raise_bet(amount)

        next_player = await self.get_next_active_player(room)
        room.current_player = next_player
        await sync_to_async(player.save)()
        await sync_to_async(room.save)()
        await self.broadcast_game_update(room)

    async def get_next_active_player(self, room):
        # Получение следующего активного игрока
        players = await sync_to_async(list)(
            room.roomplayer_set.filter(is_active=True).order_by('seat_number')
        )
        current_seat = room.current_player
        next_player = next(
            (p for p in players if p.seat_number > current_seat),
            players[0] if players else None  # Если следующий игрок отсутствует, возвращаем первого
        )
        return next_player.seat_number if next_player else current_seat

    async def broadcast_game_update(self, room):
        RoomPlayer = get_room_player_model()
        players = await sync_to_async(list)(
            RoomPlayer.objects.filter(room=room).values(
                'user__username', 'current_bet', 'stack', 'role', 'is_active', 'seat_number'
            )
        )

        current_player = await sync_to_async(RoomPlayer.objects.filter)(
            room=room, seat_number=room.current_player
        ).values('user__username')

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_update',
                'message': {
                    "action": "update_game",
                    "pot": float(room.pot),
                    "current_bet": room.current_bet,
                    "players": players,
                    "current_player": current_player[0]['user__username'] if current_player else None,
                    "canFold": True,
                    "canCall": room.current_bet > 0,
                    "canCheck": room.current_bet == 0,
                    "canRaise": room.current_bet > 0,
                }
            }
        )

    async def game_update(self, event):
        await self.send(text_data=json.dumps(event['message']))

    async def player_join(self, event):
        await self.send(text_data=json.dumps({
            'action': 'player_join',
            'username': event['username'],
            'seat': event['seat'],
            'stack': event['stack'],
            'role': event['role'],
        }))

    async def start_game(self):
        if self.room.flag_is_started:
            print("Игра уже начата. Повторный запуск невозможен.")
            return
        print("ИГРА НАЧАЛАСЬ")
        # Получаем модели RoomPlayer и Room
        RoomPlayer = get_room_player_model()
        Room = get_room_model()

        # Загружаем комнату
        self.room = await Room.objects.aget(unique_id=self.room_id)  # self.room_id должен быть установлен ранее

        # Получаем список активных игроков
        self.active_players = await database_sync_to_async(
            lambda: list(RoomPlayer.objects.filter(room=self.room, is_active=1).order_by('seat_number'))
        )()
        # Инициализация префлопа, определение первого игрока после большого блайнда
        await self.preflop_betting_round()



    async def game_start(self, event):
        """
        Отправляет данные о начале игры клиентам.
        """
        await self.send(text_data=json.dumps({
            'action': 'game_start',
            'message': event['message'],
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
                if RoomPlayer.objects.filter(room=room, user=user).exists():
                    return {'error': 'You are already seated at this table!'}

                if RoomPlayer.objects.filter(room=room, seat_number=seat_number).exists():
                    return {'error': 'This seat is already taken!'}

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


    async def send_game_state(self):
        """
        Отправка текущего состояния игры всем клиентам через WebSocket
        """
        RoomPlayer = get_room_player_model()
        Room = get_room_model()

        # Загружаем текущую комнату и ее игроков
        self.room = await Room.objects.aget(unique_id=self.room_id)
        players = await database_sync_to_async(
            lambda: list(RoomPlayer.objects.filter(room=self.room, is_active=1).order_by('seat_number'))
        )()

        # Подготавливаем данные для отправки
        game_state = {
            'pot': float(self.room.pot),
            'players': [
                {
                    'seat_number': player.seat_number,
                    'stack': float(player.stack),
                    'role': player.role
                }
                for player in players
            ]
        }

        # Отправляем данные всем клиентам в группе
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_state_update',
                'message': game_state
            }
        )

    async def game_state_update(self, event):
        """
        Получение состояния игры и отправка его клиенту
        """
        await self.send(text_data=json.dumps({
            'action': 'game_state_update',
            'message': event['message'],
        }))

    async def initialize_preflop(self, room):
        # Получить всех игроков в комнате, отсортированных по seat_number
        RoomPlayer = get_room_player_model()
        players = await sync_to_async(list)(
            RoomPlayer.objects.filter(room=room, is_active=True).order_by('seat_number')
        )

        # Найти игрока с ролью Big Blind
        big_blind_player = next((p for p in players if p.role == "Big Blind"), None)

        if not big_blind_player:
            raise ValueError("Не найден игрок с ролью Big Blind!")

        # Определить следующего игрока по seat_number
        next_player = next(
            (p for p in players if p.seat_number > big_blind_player.seat_number),
            players[0] if players else None  # Если следующий игрок отсутствует, вернемся к первому
        )

        if next_player:
            room.current_player = next_player.seat_number
            await sync_to_async(room.save)()

    async def preflop_betting_round(self):
        """Инициализирует раунд торгов на префлопе, выбор доступен только текущему игроку."""
        await self.collect_blinds()  # Сбор блайндов

        len_of_players = len(self.active_players)

        if len_of_players < 2:
            # Недостаточно игроков
            await self.broadcast_game_update(self.room)
            return

        while not await self.deal_is_over():
            # Получаем текущего игрока
            current_player_seat = self.room.current_player
            current_player = next(
                (player for player in self.active_players if player.seat_number == current_player_seat),
                None
            )

            if not current_player or not current_player.is_active:
                # Если текущий игрок не найден или выбыл, переключаем на следующего
                self.room.current_player = await self.get_next_active_player(self.room)
                await sync_to_async(self.room.save)()
                continue

            # Даём текущему игроку возможность сделать ход
            await self.answer_on_bet(current_player)

            # Проверяем, завершена ли раздача
            if await self.deal_is_over():
                break

            # Переход хода к следующему игроку
            self.room.current_player = await self.get_next_active_player(self.room)
            await sync_to_async(self.room.save)()

        # Завершаем раздачу, если осталось 1 или менее активных игроков
        if await self.deal_is_over():
            return

    async def bb_index(self):
        """Находит индекс игрока после большого блайнда."""
        RoomPlayer = get_room_player_model()
        # Загружаем активных игроков из базы данных
        players = await database_sync_to_async(
            lambda: list(RoomPlayer.objects.filter(room=self.room, is_active=1).order_by('seat_number'))
        )()
        self.active_players = players  # Инициализация active_players для дальнейшего использования

        # Находим игрока на позиции большого блайнда
        big_blind_player = next((p for p in players if p.role == "Big Blind"), None)
        if not big_blind_player:
            raise ValueError("Не найден игрок на позиции Big Blind")

        # Определяем индекс следующего игрока после большого блайнда
        bb_index = players.index(big_blind_player)
        return (bb_index + 1) % len(players)  # Следующий игрок

    async def collect_blinds(self):
        """
        Собирает блайнды и назначает роли (Dealer, Small Blind, Big Blind).
        Переход блайндов не реализован — роли назначаются статически.
        """
        if len(self.active_players) < 2:
            # Недостаточно игроков для начала раздачи
            await self.send(text_data=json.dumps({
                'action': 'error',
                'message': 'Недостаточно игроков для начала игры.'
            }))
            return

        # Назначаем роли в зависимости от количества игроков
        if len(self.active_players) == 2:
            # Heads-up: первый игрок — Dealer (он же Small Blind), второй — Big Blind
            dealer = self.active_players[0]
            bb = self.active_players[1]

            dealer.role = 'Dealer'  # В Heads-Up дилер всегда Small Blind
            dealer.role = 'Small Blind'
            bb.role = 'Big Blind'

            # Собираем блайнды
            small_blind_amount = self.room.big_blind / 2
            big_blind_amount = self.room.big_blind

            dealer.stack -= small_blind_amount
            bb.stack -= big_blind_amount
            self.room.pot = small_blind_amount + big_blind_amount
            self.room.current_bet = big_blind_amount

            # Сохраняем изменения
            await sync_to_async(dealer.save)()
            await sync_to_async(bb.save)()
            await sync_to_async(self.room.save)()

        elif len(self.active_players) >= 3:
            # Если игроков >= 3: первый игрок — Dealer, второй — Small Blind, третий — Big Blind
            dealer = self.active_players[0]
            sb = self.active_players[1]
            bb = self.active_players[2]

            dealer.role = 'Dealer'
            sb.role = 'Small Blind'
            bb.role = 'Big Blind'

            # Собираем блайнды
            small_blind_amount = self.room.big_blind / 2
            big_blind_amount = self.room.big_blind

            sb.stack -= small_blind_amount
            bb.stack -= big_blind_amount
            self.room.pot = small_blind_amount + big_blind_amount
            self.room.current_bet = big_blind_amount

            # Сохраняем изменения
            await sync_to_async(dealer.save)()
            await sync_to_async(sb.save)()
            await sync_to_async(bb.save)()
            await sync_to_async(self.room.save)()

        # Передаём обновлённое состояние игры клиентам
        await self.send_game_state()

        # Отправляем обновление через канал
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_start',
                'message': {
                    'dealer': self.active_players[0].seat_number,
                    'small_blind': self.active_players[1].seat_number if len(self.active_players) > 1 else None,
                    'big_blind': self.active_players[2].seat_number if len(self.active_players) > 2 else None,
                    'pot': self.room.pot,
                    'current_bet': self.room.current_bet,
                    'current_player': self.room.current_player,
                }
            }
        )

    async def answer_on_bet(self, player):
        """Даёт текущему игроку возможность сделать ход."""
        await self.send(text_data=json.dumps({
            'action': 'update_buttons',
            'canFold': True,
            'canCall': self.room.current_bet > player.current_bet,
            'canCheck': self.room.current_bet == player.current_bet,
            'canRaise': player.stack > self.room.current_bet
        }))

        # Ожидаем действия от клиента
        action_data = await self.wait_for_action(player)

        # Обрабатываем действия игрока
        action = action_data.get('action')
        amount = action_data.get('amount', 0)

        if action == 'fold':
            await self.player_fold(player)
        elif action == 'call':
            await self.player_call(player)
        elif action == 'check':
            await self.player_check(player)
        elif action == 'raise':
            await self.player_raise(player, amount)

    async def preflop_bb_check(self, player):
        """Дает игроку на позиции Big Blind уникальные опции на префлопе."""
        await self.send(text_data=json.dumps({
            'action': 'update_buttons',
            'canFold': True,
            'canCheck': self.room.current_bet == player.current_bet,
            'canRaise': player.stack > self.room.current_bet
        }))

        action_data = await self.wait_for_action(player)

        action = action_data.get('action')
        amount = action_data.get('amount', 0)

        if action == 'fold':
            await self.player_fold(player)
        elif action == 'check':
            await self.player_check(player)
        elif action == 'raise':
            await self.player_raise(player, amount)

    async def equality_of_bets(self):
        """Проверяет, уравнялись ли ставки всех игроков."""
        self.active_bets = [
            player.current_bet for player in self.active_players if player.is_active
        ]
        return all(bet == self.current_bet for bet in self.active_bets)

    async def deal_is_over(self):
        """Проверяет, закончилась ли текущая раздача."""
        # Раздача заканчивается, если в игре остался один игрок
        active_players_count = len([player for player in self.active_players if player.is_active])
        if active_players_count == 1:
            winner = [player for player in self.active_players if player.is_active][0]
            await self.end_deal(winner)
            return True
        return False

    async def end_deal(self, winner):
        """Завершает раздачу, передает банк победителю."""
        self.room.pot += sum(player.current_bet for player in self.active_players)
        winner.stack += self.room.pot
        self.room.pot = 0
        await self.broadcast_game_update(self.room)

    async def player_check(self, player):
        """Игрок пропускает, если ставка нулевая."""
        if player.current_bet != self.room.current_bet:
            raise ValueError(
                f"{player.user.username} не может сделать чек, так как его ставка не равна текущей ({self.room.current_bet}).")
        await self.broadcast_game_update(self.room)

    async def player_fold(self, player):
        """Игрок сбрасывает карты и выходит из раунда."""
        player.is_active = False
        await database_sync_to_async(player.save)()
        await self.broadcast_game_update(self.room)

    async def player_call(self, player):
        """Игрок уравнивает ставку."""
        call_amount = self.room.current_bet - player.current_bet
        if call_amount > player.stack:
            raise ValueError(f"{player.user.username} не хватает денег для уравнивания ставки ({call_amount}).")

        player.stack -= call_amount
        player.current_bet += call_amount
        self.room.pot += call_amount

        await database_sync_to_async(player.save)()
        await database_sync_to_async(self.room.save)()
        await self.broadcast_game_update(self.room)

    async def player_bet(self, player, amount):
        """Игрок делает ставку."""
        if amount > player.stack:
            raise ValueError(f"{player.user.username} не хватает денег для ставки ({amount}).")

        player.stack -= amount
        player.current_bet += amount
        self.room.pot += amount
        self.room.current_bet = player.current_bet

        await database_sync_to_async(player.save)()
        await database_sync_to_async(self.room.save)()
        await self.broadcast_game_update(self.room)

    async def player_raise(self, player, amount):
        """Игрок повышает ставку."""
        raise_amount = amount - player.current_bet
        if raise_amount <= 0:
            raise ValueError("Размер рейза должен быть больше текущей ставки.")
        if raise_amount > player.stack:
            raise ValueError(f"{player.user.username} не хватает денег для рейза ({raise_amount}).")

        player.stack -= raise_amount
        player.current_bet = amount
        self.room.pot += raise_amount
        self.room.current_bet = amount

        await database_sync_to_async(player.save)()
        await database_sync_to_async(self.room.save)()
        await self.broadcast_game_update(self.room)

    async def wait_for_action(self, player):
        """Ожидает действия от текущего игрока."""
        while True:
            data = await self.receive()
            action = json.loads(data)
            if action.get('player') == player.user.username:
                return action
