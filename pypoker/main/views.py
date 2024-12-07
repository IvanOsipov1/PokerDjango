from django.shortcuts import render
from django.contrib import messages


def index(request):
    return render(request, 'main/menu.html')


def some_view(request):
    messages.success(request, "Сообщение об успешном действии.")
    return render(request, 'main/menu.html')


def get_rooms(request):
    return render(request, 'main/room_list.html')