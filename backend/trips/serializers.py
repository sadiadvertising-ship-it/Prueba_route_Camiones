from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .services import ors
from .services.geocoding import geocode

# Open-Meteo forecasts 16 days ahead; a week leaves room for the longest haul
# plus the 48 h heatmap window.
MAX_DAYS_AHEAD = 7


class TripSerializer(serializers.Serializer):
    origin = serializers.CharField()
    destination = serializers.CharField()
    departure = serializers.DateTimeField()
    weight_lb = serializers.IntegerField(min_value=1)
    interval = serializers.ChoiceField(choices=[10, 25, 50], required=False, allow_null=True)

    def validate_origin(self, text):
        return place(text)

    def validate_destination(self, text):
        return place(text)

    def validate_departure(self, when):
        # The forecast is hourly, so a departure earlier in the current hour still has data.
        now = timezone.now()
        if when < now.replace(minute=0, second=0, microsecond=0):
            raise serializers.ValidationError("Departure cannot be in the past.")
        if when > now + timedelta(days=MAX_DAYS_AHEAD):
            raise serializers.ValidationError(f"Departure must be within the next {MAX_DAYS_AHEAD} days.")
        return when


def place(text):
    try:
        return geocode(text)
    except ors.PlaceNotFound as exc:
        raise serializers.ValidationError(str(exc))


class AssessSerializer(serializers.Serializer):
    ticket = serializers.CharField()
    forecasts = serializers.ListField(child=serializers.JSONField(), allow_empty=False)
