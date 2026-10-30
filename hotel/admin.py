from django.contrib import admin

from .models import Charge, Guest, Reservation, Room

admin.site.register(Guest)
admin.site.register(Room)
admin.site.register(Reservation)
admin.site.register(Charge)
