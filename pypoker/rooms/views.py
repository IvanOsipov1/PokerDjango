from django.shortcuts import render
from django.apps import apps

Room = apps.get_model('main', 'Room')

def room_details(request, room_id):
    room = Room.objects.get(unique_id=room_id)
    return render(request, 'rooms/room_2_players.html', {'room': room})
