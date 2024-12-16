from django.shortcuts import render, get_object_or_404
from django.apps import apps

Room = apps.get_model('main', 'Room')
RoomPlayer = apps.get_model('rooms', 'RoomPlayer')



def room_detail(request, unique_id):
    room = get_object_or_404(Room, unique_id=unique_id)
    players = RoomPlayer.objects.filter(room=room)
    seats = range(1, 3)  # допустим, у вас есть количество мест
    return render(request, 'rooms/room_2_players.html', {
        'room': room,
        'players': players,
        'seats': seats
    })

