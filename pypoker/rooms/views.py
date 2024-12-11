from django.shortcuts import render, get_object_or_404
from main.models import Room  # Используем модель Room из приложения main
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Player
import json

# def room_detail(request, room_id):
#     room = get_object_or_404(Room, unique_id=room_id)
#     return render(request, 'rooms/room_details.html', {'room': room})


def room_view(request, room_id):
    # Используем unique_id для поиска комнаты
    room = get_object_or_404(Room, unique_id=room_id)
    players = room.max_players

    # Определяем шаблон в зависимости от количества игроков
    if players == 2:
        template_name = 'rooms/room_2_players.html'
    elif players == 3:
        template_name = 'rooms/room_3_players.html'
    else:
        template_name = 'rooms/room_details.html'  # На случай других конфигураций

    return render(request, template_name, {'room': room})


@csrf_exempt
def sit_player(request, player_id):
    room = Room.objects.get(unique_id=room_id)

    if request.method == "POST":
        data = json.loads(request.body)
        stack = data.get("stack")

        # Проверим, не превышает ли количество игроков максимальное
        if room.players.count() >= room.max_players:
            return JsonResponse({'success': False, 'error': 'Мест нет'}, status=400)

        # Добавляем игрока в комнату с выбранным стеком
        player = Player.objects.create(user=request.user, room=room, stack=stack)

        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

# views.py

def exit_room(request, room_id):
    room = Room.objects.get(unique_id=room_id)
    player = room.players.get(user=request.user)
    player.delete()  # Удаляем игрока из комнаты

    return JsonResponse({'success': True})
