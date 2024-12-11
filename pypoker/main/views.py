from django.shortcuts import render
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from .models import Room
from django.views.decorators.csrf import csrf_exempt

def menu(request):
    return render(request, 'main/menu.html')


def some_view(request):
    messages.success(request, "Сообщение об успешном действии.")
    return render(request, 'main/menu.html')


def get_rooms(request):
    return render(request, 'main/room_list.html')


def index(request):
    return render(request, 'index.html')



# Представление для создания комнаты
@csrf_exempt
def create_room(request):
    if request.method == 'POST':
        max_players = request.POST.get('players')
        big_blind = int(request.POST.get('big_blind'))
        small_blind = big_blind // 2  # Малый блайнд — половина большого
        blinds = f"{small_blind}/{big_blind}"
        room = Room.objects.create(max_players=max_players, blinds=blinds)
        return JsonResponse({'room_id': room.unique_id})
    return JsonResponse({'error': 'Invalid request'}, status=400)

# Представление для отображения комнаты по уникальному идентификатору
def room_detail(request, room_id):
    room = get_object_or_404(Room, unique_id=room_id)
    return render(request, 'main/room_detail.html', {'room': room})

# Представление для списка комнат
def get_rooms(request):
    rooms = Room.objects.all()
    return render(request, 'main/room_list.html', {'rooms': rooms})