// Изменение текста кнопок
document.getElementById('btn1').innerText = 'New Text 1';
document.getElementById('btn2').innerText = 'New Text 2';
document.getElementById('btn3').innerText = 'New Text 3';
document.getElementById('btn4').innerText = 'New Text 4';

// Изменение текста username
document.getElementById('username').innerText = 'New Username'; // Замените на нужный текст

// Функция для переключения видимости меню
function toggleMenu() {
    const menu = document.getElementById('dropdownMenu');
    const isVisible = menu.style.display === 'block';
    menu.style.display = isVisible ? 'none' : 'block';
}

// Функция для выхода (заглушка)
function logout() {
    alert('You clicked Logout!');
}