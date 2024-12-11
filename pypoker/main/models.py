import uuid
from django.db import models

class Room(models.Model):
    name = models.CharField(max_length=255, default="Новая комната")
    max_players = models.PositiveIntegerField(default=10)
    blinds = models.CharField(max_length=20)
    unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return f"Room {self.name} - ID: {self.unique_id}"