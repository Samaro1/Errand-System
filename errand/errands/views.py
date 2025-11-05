from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Errand
from .serializers import ErrandSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def all_errands(request):
    """Return a list of all errands."""
    errands = Errand.objects.all()
    serializer = ErrandSerializer(errands, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_completed(request, errand_id):
    """Mark an errand as awaiting approval by the creator."""
    errand = get_object_or_404(Errand, id=errand_id)

    # Ensure the logged-in user is the assigned runner
    if errand.runner != request.user:
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

    errand.status = "awaiting_approval"
    errand.save()

    serializer = ErrandSerializer(errand)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_completion(request, errand_id):
    """Approve an errand as completed (by the creator)."""
    errand = get_object_or_404(Errand, id=errand_id)

    # Ensure the logged-in user is the creator
    if errand.user != request.user:
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

    errand.status = "completed"
    errand.save()

    # TODO: trigger payment release logic here
    # release_payment(errand.runner, errand.price)

    serializer = ErrandSerializer(errand)
    return Response(serializer.data, status=status.HTTP_200_OK)
