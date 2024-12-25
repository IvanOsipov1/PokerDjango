from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model


class RoomPlayer(models.Model):
    ROLE_CHOICES = [
        ('Dealer', 'Dealer'),
        ('Small Blind', 'Small Blind'),
        ('Big Blind', 'Big Blind'),
        ('Player', 'Player'),
    ]
    def get_user(self):
        return get_user_model()
    user = models.ForeignKey(
        'users.CustomUser',  # Используем строковую ссылку на модель пользователя
        on_delete=models.CASCADE,
        related_name="room_players"
    )
    room = models.ForeignKey(
        'main.Room',
        on_delete=models.CASCADE,
        related_name="players"
    )
    stack = models.FloatField(default=0.0)
    seat_number = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, default="active")
    last_action = models.CharField(max_length=20, null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Player')
    is_active = models.BooleanField(default=True)
    current_bet = models.PositiveIntegerField(default=0,
                                              verbose_name="Активная ставка игрока")  # Ставка игрока на текущей улице
    def assign_role(self, role):
        self.role = role
        self.save()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['room', 'user'], name='unique_user_in_room'),
            models.UniqueConstraint(fields=['room', 'seat_number'], name='unique_seat_in_room')
        ]

    def __str__(self):
        return f"{self.user.username} in {self.room.name} (Seat {self.seat_number})"
