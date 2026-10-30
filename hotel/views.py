from decimal import Decimal

from django.db import connection, transaction
from django.db.models import ProtectedError
from django.http import JsonResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Charge, Guest, Reservation, Room
from .serializers import ChargeSerializer, GuestSerializer, ReservationSerializer, RoomSerializer


def health(request):
    """Проверка, что бэкенд жив и видит базу."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse(
        {
            "status": "ok",
            "guests": Guest.objects.count(),
            "rooms": Room.objects.count(),
            "reservations": Reservation.objects.count(),
        }
    )


class ProtectedDeleteMixin:
    """Нельзя удалить гостя или номер, у которых есть бронирования: отвечаем 409, а не 500."""

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Cannot delete: there are reservations linked to this object."},
                status=status.HTTP_409_CONFLICT,
            )


class GuestViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    queryset = Guest.objects.all()
    serializer_class = GuestSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        last_name = self.request.query_params.get("last_name")
        if last_name:
            qs = qs.filter(last_name__icontains=last_name)
        return qs


class RoomViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        if p.get("room_type"):
            qs = qs.filter(room_type=p["room_type"])
        return qs


class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.select_related("guest", "room").all()
    serializer_class = ReservationSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        for field in ("status", "guest", "room"):
            if p.get(field):
                qs = qs.filter(**{field: p[field]})
        return qs

    def _conflict(self, message):
        return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="check-in")
    def check_in(self, request, pk=None):
        """Заезд: номер должен быть чистым; на счёт гостя начисляется стоимость проживания."""
        reservation = self.get_object()
        if reservation.status != Reservation.BOOKED:
            return self._conflict(f"Cannot check in: reservation is '{reservation.status}'.")
        room = reservation.room
        if room.status != Room.CLEAN:
            return self._conflict(f"Cannot check in: room {room.number} is '{room.status}', not clean.")

        with transaction.atomic():
            Charge.objects.create(
                reservation=reservation,
                kind=Charge.CHARGE,
                description=f"Room charge: {reservation.nights} night(s) x {room.rate_per_night}",
                amount=room.rate_per_night * reservation.nights,
            )
            reservation.status = Reservation.CHECKED_IN
            reservation.save(update_fields=["status"])
        return Response(self.get_serializer(reservation).data)

    @action(detail=True, methods=["post"], url_path="check-out")
    def check_out(self, request, pk=None):
        """Выезд: счёт должен быть закрыт (баланс 0). Номер становится грязным."""
        reservation = self.get_object()
        if reservation.status != Reservation.CHECKED_IN:
            return self._conflict(f"Cannot check out: reservation is '{reservation.status}'.")
        _, _, balance = reservation.folio_totals()
        if balance != 0:
            return self._conflict(f"Cannot check out: folio balance is {balance}, it must be 0.")

        with transaction.atomic():
            reservation.status = Reservation.CHECKED_OUT
            reservation.save(update_fields=["status"])
            room = reservation.room
            room.status = Room.DIRTY
            room.save(update_fields=["status"])
        return Response(self.get_serializer(reservation).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        reservation = self.get_object()
        if reservation.status != Reservation.BOOKED:
            return self._conflict(f"Cannot cancel: reservation is '{reservation.status}'.")
        reservation.status = Reservation.CANCELLED
        reservation.save(update_fields=["status"])
        return Response(self.get_serializer(reservation).data)

    @action(detail=True, methods=["get"])
    def folio(self, request, pk=None):
        """Счёт гостя: все строки, суммы начислений и оплат, баланс."""
        reservation = self.get_object()
        charges, payments, balance = reservation.folio_totals()
        return Response(
            {
                "reservation": reservation.pk,
                "guest_name": reservation.guest.full_name,
                "room_number": reservation.room.number,
                "status": reservation.status,
                # Деньги везде строками с двумя знаками, как в /api/charges/
                "total_charges": str(charges.quantize(Decimal("0.01"))),
                "total_payments": str(payments.quantize(Decimal("0.01"))),
                "balance": str(balance.quantize(Decimal("0.01"))),
                "lines": ChargeSerializer(reservation.charges.all(), many=True).data,
            }
        )


class ChargeViewSet(viewsets.ModelViewSet):
    queryset = Charge.objects.select_related("reservation").all()
    serializer_class = ChargeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("reservation"):
            qs = qs.filter(reservation=p["reservation"])
        if p.get("kind"):
            qs = qs.filter(kind=p["kind"])
        return qs
