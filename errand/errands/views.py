from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import Errand, Review
from .serializers import ErrandSerializer
from user.models import Customer
from payment.models import Payment
from payment.utils import release_payment, refund_payment
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages

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
    # Time filters: created_within=<minutes>, created_after=<ISO datetime>, created_before=<ISO datetime>
    created_within = request.GET.get("created_within")
    created_after = request.GET.get("created_after")
    created_before = request.GET.get("created_before")

    if creator_id:
        errands = errands.filter(creator_id=creator_id)
    if runner_id:
        errands = errands.filter(runner_id=runner_id)
    if status_filter:
        errands = errands.filter(status=status_filter)

    # Created within: integer minutes
    if created_within:
        try:
            mins = int(created_within)
            since = timezone.now() - timezone.timedelta(minutes=mins)
            errands = errands.filter(created_at__gte=since)
        except Exception:
            pass

    # Created after/before via ISO datetimes
    if created_after:
        dt = parse_datetime(created_after)
        if dt:
            errands = errands.filter(created_at__gte=dt)
    if created_before:
        dt2 = parse_datetime(created_before)
        if dt2:
            errands = errands.filter(created_at__lte=dt2)

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


# ------------------ WEB VIEWS (server rendered) ------------------ #
@login_required
def web_errand_list(request):
    # Show public/available errands (only those posted and not taken). Creators
    # should always be able to see their own errands (including payment_pending)
    from django.db.models import Q

    available = Errand.objects.filter(status="pending", runner__isnull=True).order_by('-created_at')
    my_errands = Errand.objects.filter(creator=request.user).order_by('-created_at')

    return render(request, "errands/list.html", {"available_errands": available, "my_errands": my_errands})


@login_required
def web_dashboard(request):
    """Simple dashboard: greeting, available errands, errands posted by self, and reviews given."""
    username = getattr(request.user, "username", "User")
    available = Errand.objects.filter(status="pending", runner__isnull=True).order_by('-created_at')
    my_errands = Errand.objects.filter(creator=request.user).order_by('-created_at')
    my_reviews = Review.objects.filter(reviewer=request.user).select_related('runner', 'errand').order_by('-created_at')

    # Errands the current user has accepted (as runner)
    accepted_errands = Errand.objects.filter(runner=request.user).order_by('-created_at')

    return render(request, "errands/dashboard.html", {
        "greeting": f"Hello, {username}",
        "available_errands": available,
        "my_errands": my_errands,
        "my_reviews": my_reviews,
        "accepted_errands": accepted_errands,
    })


@login_required
@csrf_protect
def web_create_errand(request):
    # Simple illegal-content checker: warns on first submit, requires confirmation to proceed.
    # Load keywords from settings if available, otherwise fall back to a reasonable default
    from django.conf import settings
    ILLEGAL_KEYWORDS = getattr(settings, "ILLEGAL_KEYWORDS", [
        "drugs",
        "cocaine",
        "heroin",
        "meth",
        "weapon",
        "weapons",
        "gun",
        "firearm",
        "bomb",
        "explosive",
        "kill",
        "murder",
        "assault",
        "steal",
        "fraud",
        "hack",
        "illegal",
    ])

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        price = request.POST.get("price", "").strip()
        confirm = request.POST.get("confirm")

        # Basic validation
        if not title or not price:
            return render(request, "errands/create.html", {"error": "Title and price required", "title": title, "description": description, "price": price})

        # Check for illegal keywords in title or description (case-insensitive)
        text = f"{title} {description}".lower()
        found = [kw for kw in ILLEGAL_KEYWORDS if kw in text]

        if found and not confirm:
            # Warn and re-render form for explicit confirmation
            messages.warning(request, "Your errand text contains terms that may indicate illegal activity: " + ", ".join(found) + ". Please confirm you want to proceed.")
            return render(request, "errands/create.html", {"warned": True, "title": title, "description": description, "price": price})
        # proceed to create but mark as pending payment and redirect to payment page
        errand = Errand.objects.create(creator=request.user, title=title, description=description, price=price, status="payment_pending")
        messages.info(request, "Errand created but pending payment. Please complete payment to post the errand.")
        # redirect to the payment initialization page for this errand
        from django.urls import reverse
        init_url = reverse("payment:web_initialize_payment") + f"?errand_id={errand.id}"
        return redirect(init_url)

    # GET: render empty form
    return render(request, "errands/create.html")


@login_required
def web_errand_detail(request, errand_id):
    errand = get_object_or_404(Errand, id=errand_id)
    payments = Payment.objects.filter(errand=errand)
    return render(request, "errands/detail.html", {"errand": errand, "payments": payments})


@login_required
@csrf_protect
def web_accept_errand(request, errand_id):
    errand = get_object_or_404(Errand, id=errand_id)
    if errand.runner:
        messages.error(request, "Errand already taken.")
        return redirect("errands:detail", errand_id=errand.id)

    if request.user == errand.creator:
        messages.error(request, "Creator cannot accept their own errand.")
        return redirect("errands:detail", errand_id=errand.id)

    errand.runner = request.user
    errand.status = "active"
    errand.save()
    messages.success(request, "Errand accepted.")
    return redirect("errands:detail", errand_id=errand.id)


@login_required
@csrf_protect
def web_mark_completed(request, errand_id):
    errand = get_object_or_404(Errand, id=errand_id)
    if errand.runner != request.user:
        messages.error(request, "Only the runner can mark this errand completed.")
        return redirect("errands:detail", errand_id=errand.id)

    errand.status = "awaiting_approval"
    errand.save()
    messages.success(request, "Errand marked as completed and awaiting approval.")
    return redirect("errands:detail", errand_id=errand.id)


@login_required
@csrf_protect
def web_approve_completion(request, errand_id):
    errand = get_object_or_404(Errand, id=errand_id)
    if errand.creator != request.user:
        messages.error(request, "Only the creator can approve completion.")
        return redirect("errands:detail", errand_id=errand.id)

    errand.status = "completed"
    errand.approved = True
    errand.save()

    payments = Payment.objects.filter(errand=errand, payer=errand.creator)
    for p in payments:
        if not p.refunded:
            try:
                release_payment(p)
            except Exception:
                # swallow provider errors for demo
                pass

    messages.success(request, "Errand approved; payment release attempted.")
    return redirect("errands:detail", errand_id=errand.id)


@login_required
@csrf_protect
def web_delete_errand(request, errand_id):
    errand = get_object_or_404(Errand, id=errand_id)
    if errand.creator != request.user:
        messages.error(request, "Only the creator can delete this errand.")
        return redirect("errands:detail", errand_id=errand.id)

    if not errand.runner:
        payments = Payment.objects.filter(errand=errand, payer=errand.creator)
        for p in payments:
            try:
                refund_payment(p, reason="Errand deleted before being taken")
            except Exception:
                pass

    errand.delete()
    messages.success(request, "Errand deleted.")
    return redirect("errands:list")


def root_dispatch(request):
    """If the request is from an authenticated or JSON-accepting client, return
    the API errands list; otherwise redirect anonymous browser users to the
    session-based login page.
    """
    accept = request.META.get("HTTP_ACCEPT", "")
    # Heuristic: if the client does not explicitly accept JSON, treat it as a browser
    # and route to the session-based pages. Authenticated browsers should land on
    # the dashboard; anonymous browsers go to login.
    if "application/json" not in accept:
        if request.user.is_authenticated:
            from django.urls import reverse
            return redirect(reverse("errands:dashboard"))
        return redirect("/user/web/login/")

    # Otherwise (API client expecting JSON) call the API view and return its response.
    try:
        resp = all_errands(request)
    except Exception:
        resp = None

    # If DRF returned something other than 403 (e.g. 200 for authenticated tests), return it.
    if resp is not None and getattr(resp, "status_code", None) != 403:
        return resp

    # Return whatever the API view produced (possibly a 403)
    return resp
