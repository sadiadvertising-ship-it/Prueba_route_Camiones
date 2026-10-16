from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import TripSerializer
from .services import ors, planning, weather


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["POST"])
def plan(request):
    form = TripSerializer(data=request.data)
    # Validation geocodes both places, so an ORS outage can surface from is_valid() too.
    try:
        if not form.is_valid():
            return Response(form.errors, status=400)
        trip = planning.plan(**form.validated_data)
    except planning.SamePlace as exc:
        return Response({"destination": [str(exc)]}, status=400)
    except (ors.ORSError, weather.WeatherError) as exc:
        return Response({"detail": str(exc)}, status=502)
    return Response(trip)
