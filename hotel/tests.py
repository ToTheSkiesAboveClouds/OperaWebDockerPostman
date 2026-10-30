from decimal import Decimal

from rest_framework.test import APITestCase

from .models import Guest, Room


class HotelApiTests(APITestCase):
    def setUp(self):
        self.guest = Guest.objects.create(first_name="Aida", last_name="Nur", email="aida@example.com")
        self.room = Room.objects.create(number="T1", floor=1, room_type="double", capacity=2, rate_per_night="30000.00")

    def reserve(self, check_in, check_out, room=None, guest=None, adults=1):
        return self.client.post(
            "/api/reservations/",
            {
                "guest": (guest or self.guest).id,
                "room": (room or self.room).id,
                "check_in": check_in,
                "check_out": check_out,
                "adults": adults,
            },
            format="json",
        )

    # ---- CRUD ----
    def test_guest_crud(self):
        r = self.client.post("/api/guests/", {"first_name": "Ivan", "last_name": "Petrov", "email": "ivan@example.com"}, format="json")
        self.assertEqual(r.status_code, 201)
        gid = r.json()["id"]
        self.assertEqual(self.client.get(f"/api/guests/{gid}/").status_code, 200)
        self.assertEqual(self.client.get("/api/guests/").json()["count"], 2)
        r = self.client.put(
            f"/api/guests/{gid}/",
            {"first_name": "Ivan", "last_name": "Sidorov", "email": "ivan@example.com"},
            format="json",
        )
        self.assertEqual(r.json()["last_name"], "Sidorov")
        self.assertEqual(self.client.patch(f"/api/guests/{gid}/", {"phone": "+77001112233"}, format="json").json()["phone"], "+77001112233")
        self.assertEqual(self.client.delete(f"/api/guests/{gid}/").status_code, 204)
        self.assertEqual(self.client.get(f"/api/guests/{gid}/").status_code, 404)

    def test_duplicate_email_rejected(self):
        r = self.client.post("/api/guests/", {"first_name": "X", "last_name": "Y", "email": "aida@example.com"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_room_crud(self):
        r = self.client.post(
            "/api/rooms/",
            {"number": "T2", "floor": 2, "room_type": "suite", "capacity": 4, "rate_per_night": "60000.00"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["status"], "clean")
        rid = r.json()["id"]
        self.assertEqual(self.client.patch(f"/api/rooms/{rid}/", {"status": "out_of_order"}, format="json").json()["status"], "out_of_order")
        self.assertEqual(self.client.get("/api/rooms/?status=out_of_order").json()["count"], 1)
        self.assertEqual(self.client.delete(f"/api/rooms/{rid}/").status_code, 204)

    # ---- Бронирования ----
    def test_reservation_create_and_update(self):
        r = self.reserve("2026-12-10", "2026-12-12")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["nights"], 2)
        self.assertEqual(r.json()["status"], "booked")
        rid = r.json()["id"]
        r = self.client.patch(f"/api/reservations/{rid}/", {"adults": 2}, format="json")
        self.assertEqual(r.json()["adults"], 2)
        self.assertEqual(self.client.delete(f"/api/reservations/{rid}/").status_code, 204)

    def test_overlap_rejected_back_to_back_allowed(self):
        self.reserve("2026-12-10", "2026-12-12")
        for ci, co in [("2026-12-11", "2026-12-13"), ("2026-12-09", "2026-12-11"), ("2026-12-10", "2026-12-12"), ("2026-12-08", "2026-12-15")]:
            self.assertEqual(self.reserve(ci, co).status_code, 400, (ci, co))
        self.assertEqual(self.reserve("2026-12-12", "2026-12-14").status_code, 201)

    def test_checkout_before_checkin_rejected(self):
        self.assertEqual(self.reserve("2026-12-12", "2026-12-10").status_code, 400)
        self.assertEqual(self.reserve("2026-12-12", "2026-12-12").status_code, 400)

    def test_over_capacity_and_out_of_order_rejected(self):
        self.assertEqual(self.reserve("2026-12-10", "2026-12-12", adults=3).status_code, 400)
        self.room.status = Room.OUT_OF_ORDER
        self.room.save()
        self.assertEqual(self.reserve("2026-12-10", "2026-12-12").status_code, 400)

    def test_cancelled_reservation_frees_room(self):
        rid = self.reserve("2026-12-10", "2026-12-12").json()["id"]
        self.assertEqual(self.client.post(f"/api/reservations/{rid}/cancel/").json()["status"], "cancelled")
        self.assertEqual(self.reserve("2026-12-10", "2026-12-12").status_code, 201)

    # ---- Полный цикл: заезд, оплата, выезд ----
    def test_full_stay_flow(self):
        rid = self.reserve("2026-12-10", "2026-12-12").json()["id"]

        r = self.client.post(f"/api/reservations/{rid}/check-in/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "checked_in")

        folio = self.client.get(f"/api/reservations/{rid}/folio/").json()
        self.assertEqual(folio["total_charges"], "60000.00")  # деньги отдаются строкой
        self.assertEqual(Decimal(folio["total_charges"]), Decimal("60000.00"))
        self.assertEqual(Decimal(folio["balance"]), Decimal("60000.00"))
        self.assertEqual(len(folio["lines"]), 1)

        # С неоплаченным счётом выехать нельзя
        self.assertEqual(self.client.post(f"/api/reservations/{rid}/check-out/").status_code, 400)

        r = self.client.post("/api/charges/", {"reservation": rid, "kind": "charge", "description": "Minibar", "amount": "2500.00"}, format="json")
        self.assertEqual(r.status_code, 201)
        r = self.client.post("/api/charges/", {"reservation": rid, "kind": "payment", "description": "Card", "amount": "62500.00"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Decimal(self.client.get(f"/api/reservations/{rid}/folio/").json()["balance"]), Decimal("0.00"))

        r = self.client.post(f"/api/reservations/{rid}/check-out/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "checked_out")
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "dirty")

        # Счёт закрыт, новые строки не принимаются
        r = self.client.post("/api/charges/", {"reservation": rid, "kind": "charge", "description": "Late", "amount": "1.00"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_check_in_requires_clean_room_and_booked_status(self):
        rid = self.reserve("2026-12-10", "2026-12-12").json()["id"]
        self.room.status = Room.DIRTY
        self.room.save()
        self.assertEqual(self.client.post(f"/api/reservations/{rid}/check-in/").status_code, 400)
        self.room.status = Room.CLEAN
        self.room.save()
        self.assertEqual(self.client.post(f"/api/reservations/{rid}/check-in/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/reservations/{rid}/check-in/").status_code, 400)

    def test_cannot_edit_checked_in_reservation(self):
        rid = self.reserve("2026-12-10", "2026-12-12").json()["id"]
        self.client.post(f"/api/reservations/{rid}/check-in/")
        self.assertEqual(self.client.patch(f"/api/reservations/{rid}/", {"adults": 2}, format="json").status_code, 400)

    # ---- Charges CRUD ----
    def test_charge_crud(self):
        rid = self.reserve("2026-12-10", "2026-12-12").json()["id"]
        r = self.client.post("/api/charges/", {"reservation": rid, "kind": "charge", "description": "Laundry", "amount": "1500.00"}, format="json")
        self.assertEqual(r.status_code, 201)
        cid = r.json()["id"]
        self.assertEqual(self.client.get(f"/api/charges/?reservation={rid}").json()["count"], 1)
        self.assertEqual(self.client.get(f"/api/charges/{cid}/").json()["description"], "Laundry")
        r = self.client.put(f"/api/charges/{cid}/", {"reservation": rid, "kind": "charge", "description": "Laundry", "amount": "2000.00"}, format="json")
        self.assertEqual(r.json()["amount"], "2000.00")
        self.assertEqual(self.client.delete(f"/api/charges/{cid}/").status_code, 204)

    def test_non_positive_amount_rejected(self):
        rid = self.reserve("2026-12-10", "2026-12-12").json()["id"]
        r = self.client.post("/api/charges/", {"reservation": rid, "kind": "charge", "description": "Bad", "amount": "0"}, format="json")
        self.assertEqual(r.status_code, 400)

    # ---- Защита от удаления ----
    def test_delete_guest_or_room_with_reservations_returns_409(self):
        self.reserve("2026-12-10", "2026-12-12")
        self.assertEqual(self.client.delete(f"/api/guests/{self.guest.id}/").status_code, 409)
        self.assertEqual(self.client.delete(f"/api/rooms/{self.room.id}/").status_code, 409)

    def test_health(self):
        self.assertEqual(self.client.get("/health/").json()["status"], "ok")
