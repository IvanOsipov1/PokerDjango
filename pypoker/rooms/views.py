from django.shortcuts import render, get_object_or_404
from django.apps import apps

Room = apps.get_model('main', 'Room')
RoomPlayer = apps.get_model('rooms', 'RoomPlayer')



def room_detail(request, unique_id):
    room = get_object_or_404(Room, unique_id=unique_id)
    players = RoomPlayer.objects.filter(room=room)
    seats = range(1, room.max_players + 1)  # Список мест от 1 до max_players

    # Формируем имя шаблона на основе количества игроков
    template_name = f'rooms/room_{room.max_players}_players.html'

    return render(request, template_name, {
        'room': room,
        'players': players,
        'seats': seats,
    })
