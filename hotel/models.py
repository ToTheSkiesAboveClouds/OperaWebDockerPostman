from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum


class Guest(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    nationality = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return self.full_name


class Room(models.Model):
    SINGLE, DOUBLE, TWIN, SUITE = "single", "double", "twin", "suite"
    ROOM_TYPES = [(SINGLE, "Single"), (DOUBLE, "Double"), (TWIN, "Twin"), (SUITE, "Suite")]

    # Статусы уборки, как в Opera: чистый / грязный / вне эксплуатации
    CLEAN, DIRTY, OUT_OF_ORDER = "clean", "dirty", "out_of_order"
    STATUSES = [(CLEAN, "Clean"), (DIRTY, "Dirty"), (OUT_OF_ORDER, "Out of order")]

    number = models.CharField(max_length=10, unique=True)
    floor = models.PositiveIntegerField()
    room_type = models.CharField(max_length=10, choices=ROOM_TYPES, default=DOUBLE)
    capacity = models.PositiveIntegerField(default=2)
    rate_per_night = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    status = models.CharField(max_length=15, choices=STATUSES, default=CLEAN)

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return f"Room {self.number} ({self.room_type})"


class Reservation(models.Model):
    BOOKED, CHECKED_IN, CHECKED_OUT, CANCELLED = "booked", "checked_in", "checked_out", "cancelled"
    STATUSES = [
        (BOOKED, "Booked"),
        (CHECKED_IN, "Checked in"),
        (CHECKED_OUT, "Checked out"),
        (CANCELLED, "Cancelled"),
    ]
    # Эти статусы занимают номер на указанные даты
    ACTIVE = [BOOKED, CHECKED_IN]

    guest = models.ForeignKey(Guest, on_delete=models.PROTECT, related_name="reservations")
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="reservations")
    check_in = models.DateField()
    check_out = models.DateField()
    adults = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=15, choices=STATUSES, default=BOOKED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["check_in", "id"]
        indexes = [models.Index(fields=["room", "check_in", "check_out"])]
        constraints = [
            models.CheckConstraint(condition=Q(check_out__gt=models.F("check_in")), name="reservation_checkout_after_checkin"),
        ]

    @property
    def nights(self):
        return (self.check_out - self.check_in).days

    def folio_totals(self):
        agg = self.charges.aggregate(
            charges=Sum("amount", filter=Q(kind=Charge.CHARGE)),
            payments=Sum("amount", filter=Q(kind=Charge.PAYMENT)),
        )
        charges = agg["charges"] or Decimal("0.00")
        payments = agg["payments"] or Decimal("0.00")
        return charges, payments, charges - payments

    def __str__(self):
        return f"#{self.pk} {self.guest} / {self.room.number} {self.check_in}..{self.check_out}"


class Charge(models.Model):
    """Строка счёта гостя (folio): начисление или оплата."""

    CHARGE, PAYMENT = "charge", "payment"
    KINDS = [(CHARGE, "Charge"), (PAYMENT, "Payment")]

    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="charges")
    kind = models.CharField(max_length=10, choices=KINDS, default=CHARGE)
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["posted_at", "id"]

    def __str__(self):
        return f"{self.kind} {self.amount} ({self.description})"
