from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("trips/plan/", views.plan),
    path("trips/assess/", views.assess),
]
