from django.db import migrations

# (номер, этаж, тип, вместимость, цена за ночь в тенге)
ROOMS = [
    ("101", 1, "single", 1, "25000.00"),
    ("102", 1, "double", 2, "32000.00"),
    ("201", 2, "twin", 2, "32000.00"),
    ("202", 2, "double", 2, "34000.00"),
    ("301", 3, "double", 3, "38000.00"),
    ("1001", 10, "suite", 4, "60000.00"),
]


def seed(apps, schema_editor):
    Room = apps.get_model("hotel", "Room")
    for number, floor, room_type, capacity, rate in ROOMS:
        Room.objects.get_or_create(
            number=number,
            defaults={"floor": floor, "room_type": room_type, "capacity": capacity, "rate_per_night": rate},
        )


def unseed(apps, schema_editor):
    apps.get_model("hotel", "Room").objects.filter(number__in=[r[0] for r in ROOMS]).delete()


class Migration(migrations.Migration):
    dependencies = [("hotel", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
