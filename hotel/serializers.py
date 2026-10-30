from rest_framework import serializers

from .models import Charge, Guest, Reservation, Room


class GuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = ["id", "first_name", "last_name", "email", "phone", "nationality", "created_at"]
        read_only_fields = ["created_at"]


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ["id", "number", "floor", "room_type", "capacity", "rate_per_night", "status"]


class ReservationSerializer(serializers.ModelSerializer):
    guest_name = serializers.CharField(source="guest.full_name", read_only=True)
    room_number = serializers.CharField(source="room.number", read_only=True)
    nights = serializers.IntegerField(read_only=True)

    class Meta:
        model = Reservation
        fields = [
            "id", "guest", "guest_name", "room", "room_number",
            "check_in", "check_out", "nights", "adults", "status", "created_at",
        ]
        # Статус меняется только действиями check-in / check-out / cancel
        read_only_fields = ["status", "created_at"]

    def validate(self, attrs):
        inst = self.instance
        if inst and inst.status != Reservation.BOOKED:
            raise serializers.ValidationError({"detail": f"Only reservations with status 'booked' can be edited (current: '{inst.status}')."})

        check_in = attrs.get("check_in", getattr(inst, "check_in", None))
        check_out = attrs.get("check_out", getattr(inst, "check_out", None))
        room = attrs.get("room", getattr(inst, "room", None))
        adults = attrs.get("adults", getattr(inst, "adults", 1))

        if check_in and check_out and check_out <= check_in:
            raise serializers.ValidationError({"check_out": "check_out must be after check_in."})

        if room:
            if room.status == Room.OUT_OF_ORDER:
                raise serializers.ValidationError({"room": f"Room {room.number} is out of order."})
            if adults > room.capacity:
                raise serializers.ValidationError({"adults": f"Room {room.number} has capacity {room.capacity}, got {adults} adults."})

        if room and check_in and check_out:
            # Интервалы пересекаются, если начало одного раньше конца другого и наоборот.
            # Выезд в день заезда следующего гостя допустим.
            clash = Reservation.objects.filter(
                room=room, status__in=Reservation.ACTIVE, check_in__lt=check_out, check_out__gt=check_in
            )
            if inst:
                clash = clash.exclude(pk=inst.pk)
            other = clash.first()
            if other:
                raise serializers.ValidationError(
                    {"detail": f"Room {room.number} is already reserved from {other.check_in} to {other.check_out}."}
                )
        return attrs


class ChargeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Charge
        fields = ["id", "reservation", "kind", "description", "amount", "posted_at"]
        read_only_fields = ["posted_at"]

    def validate(self, attrs):
        reservation = attrs.get("reservation", getattr(self.instance, "reservation", None))
        if reservation and reservation.status in (Reservation.CANCELLED, Reservation.CHECKED_OUT):
            raise serializers.ValidationError(
                {"reservation": f"Folio is closed: reservation is '{reservation.status}'."}
            )
        return attrs
