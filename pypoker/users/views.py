from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, get_user_model


User = get_user_model()


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
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']

        # Проверка совпадения паролей
        if password != confirm_password:
            messages.error(request, 'Пароли не совпадают.')
            return render(request, 'users/register.html')

        # Проверка, занят ли никнейм
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Имя пользователя уже занято.')
            return render(request, 'users/register.html')

        # Проверка, занята ли почта
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Эта почта уже используется.')
            return render(request, 'users/register.html')

        # Создание пользователя
        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()
        messages.success(request, 'Регистрация успешна. Теперь вы можете войти.')
        login(request, user)
        return redirect('users:login')

    return render(request, 'users/register.html')
