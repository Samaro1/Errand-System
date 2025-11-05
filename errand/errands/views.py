from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Errand, Review
from .serializers import ErrandSerializer
from user.models import Customer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def all_errands(request):
    """Return a list of all errands."""
    errands = Errand.objects.all()
    serializer = ErrandSerializer(errands, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_errand(request):
    """Create a new errand by the logged-in user."""
    data = request.data.copy()
    data["creator"] = request.user.id  # Assign the logged-in user as creator

    serializer = ErrandSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def single_errand(request, errand_id):
    """Retrieve details of a single errand."""
    errand = get_object_or_404(Errand, id=errand_id)
    serializer = ErrandSerializer(errand)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_errand(request, errand_id):
    """Allow only the creator to delete an errand."""
    errand = get_object_or_404(Errand, id=errand_id)

    if errand.creator != request.user:
        return Response({"error": "You are not authorized to delete this errand."}, status=status.HTTP_403_FORBIDDEN)

    errand.delete()
    return Response({"message": "Errand deleted successfully."}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_errand(request, errand_id):
    """Allow a runner to accept an available errand."""
    errand = get_object_or_404(Errand, id=errand_id)

    if errand.runner:
        return Response({"error": "Errand already taken."}, status=status.HTTP_400_BAD_REQUEST)

    errand.runner = request.user
    errand.status = "active"
    errand.save()

    serializer = ErrandSerializer(errand)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_completed(request, errand_id):
    """Mark an errand as awaiting approval by the creator."""
    errand = get_object_or_404(Errand, id=errand_id)

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

    if errand.creator != request.user:
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

    errand.status = "completed"
    errand.approved = True
    errand.save()

    # Placeholder for payment release logic
    # release_payment(errand.runner, errand.price)

    serializer = ErrandSerializer(errand)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def review_errand(request, errand_id):
    """Leave a review for a completed errand."""
    errand = get_object_or_404(Errand, id=errand_id)

    if errand.creator != request.user:
        return Response({"error": "Only the creator can leave a review."}, status=status.HTTP_403_FORBIDDEN)

    if errand.status != "completed":
        return Response({"error": "You can only review completed errands."}, status=status.HTTP_400_BAD_REQUEST)

    rating = request.data.get("rating")
    feedback = request.data.get("feedback", "")

    if not rating:
        return Response({"error": "Rating is required."}, status=status.HTTP_400_BAD_REQUEST)

    Review.objects.create(
        runner=errand.runner,
        reviewer=request.user,
        errand=errand,
        rating=rating,
        feedback=feedback,
    )

    return Response({"message": "Review submitted successfully."}, status=status.HTTP_201_CREATED)
