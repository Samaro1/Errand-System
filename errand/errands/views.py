from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Errand, Review
from .serializers import ErrandSerializer
from user.models import Customer
from payment.models import Payment
from payment.utils import release_payment, refund_payment

# ------------------ ERRANDS LIST / FILTER ------------------ #
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def all_errands(request):
    """
    Return a list of errands, optionally filtered by creator, runner, or status,
    and optionally sorted by creation date, price, or any field.
    """
    errands = Errand.objects.all()

    # Filters
    creator_id = request.GET.get("creator")
    runner_id = request.GET.get("runner")
    status_filter = request.GET.get("status")

    if creator_id:
        errands = errands.filter(creator_id=creator_id)
    if runner_id:
        errands = errands.filter(runner_id=runner_id)
    if status_filter:
        errands = errands.filter(status=status_filter)

    # Optional sorting
    sort_by = request.GET.get("sort_by")
    order = request.GET.get("order", "desc")
    if sort_by:
        if order == "desc":
            sort_by = f"-{sort_by}"
        errands = errands.order_by(sort_by)
    else:
        errands = errands.order_by("-created_at")  # default newest first

    serializer = ErrandSerializer(errands, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ------------------ CREATE ERRAND ------------------ #
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_errand(request):
    """Create a new errand by the logged-in user."""
    data = request.data.copy()
    data["creator"] = request.user.id  # Assign logged-in user as creator

    serializer = ErrandSerializer(data=data, context={"request": request})
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ------------------ SINGLE ERRAND ------------------ #
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def single_errand(request, errand_id):
    """Retrieve details of a single errand."""
    errand = get_object_or_404(Errand, id=errand_id)
    serializer = ErrandSerializer(errand)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ------------------ DELETE ERRAND ------------------ #
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_errand(request, errand_id):
    """Allow only the creator to delete an errand."""
    errand = get_object_or_404(Errand, id=errand_id)
    if errand.creator != request.user:
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
    # If no one has taken the errand, refund any payments made by the creator
    # for this errand (e.g., they paid then deleted before a runner accepted).
    if not errand.runner:
        payments = Payment.objects.filter(errand=errand, payer=errand.creator)
        for p in payments:
            try:
                refund_payment(p, reason="Errand deleted before being taken")
            except NotImplementedError:
                # In live mode refund not implemented; skip and leave payment as-is
                pass

    errand.delete()
    return Response({"message": "Errand deleted successfully."}, status=status.HTTP_200_OK)


# ------------------ ACCEPT ERRAND ------------------ #
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


# ------------------ MARK COMPLETED ------------------ #
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_completed(request, errand_id):
    """Runner marks errand as awaiting approval by creator."""
    errand = get_object_or_404(Errand, id=errand_id)

    if errand.runner != request.user:
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

    errand.status = "awaiting_approval"
    errand.save()

    serializer = ErrandSerializer(errand)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ------------------ APPROVE COMPLETION ------------------ #
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_completion(request, errand_id):
    """Creator approves an errand as completed."""
    errand = get_object_or_404(Errand, id=errand_id)

    if errand.creator != request.user:
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

    errand.status = "completed"
    errand.approved = True
    errand.save()

    # Trigger payment release to the runner for any payments made on this errand.
    payments = Payment.objects.filter(errand=errand, payer=errand.creator)
    for p in payments:
        # Only release non-refunded payments
        if not p.refunded:
            try:
                release_payment(p)
            except NotImplementedError:
                # Live provider not configured; skip silently
                pass

    serializer = ErrandSerializer(errand)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ------------------ REVIEW ERRAND ------------------ #
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def review_errand(request, errand_id):
    """Creator leaves a review for completed errand."""
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
