from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import AssessSerializer, TripSerializer
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
        trip = planning.prepare(**form.validated_data)
    except planning.SamePlace as exc:
        return Response({"destination": [str(exc)]}, status=400)
    except ors.ORSError as exc:
        return Response({"detail": str(exc)}, status=502)
    return Response(trip)


@api_view(["POST"])
def assess(request):
    form = AssessSerializer(data=request.data)
    if not form.is_valid():
        return Response(form.errors, status=400)
    try:
        result = planning.assess(**form.validated_data)
    except planning.Expired as exc:
        return Response({"detail": str(exc)}, status=400)
    except weather.BadForecast as exc:
        return Response({"forecasts": [str(exc)]}, status=400)
    return Response(result)
