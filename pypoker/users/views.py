from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login


def login_user(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Вы успешно вошли в систему.')
            return redirect('home')  # Замените 'home' на имя вашего представления или URL
        else:
            messages.error(request, 'Неправильное имя пользователя или пароль.')
    return render(request, 'users/login.html')


def logout_user(request):
    return HttpResponse("logout")


def register(request):
    return HttpResponse('reg')
