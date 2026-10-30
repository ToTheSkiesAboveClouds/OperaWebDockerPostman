from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("guests", views.GuestViewSet)
router.register("rooms", views.RoomViewSet)
router.register("reservations", views.ReservationViewSet)
router.register("charges", views.ChargeViewSet)

urlpatterns = [
    path("health/", views.health),
    path("api/", include(router.urls)),
]
