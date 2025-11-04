from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Errand, Review
from django.http import HttpResponse

@login_required
def all_errands(request):
    errandz= Errand.objects.all()
    return render(request, "errand/errands.py", {
        "errands": errandz
    })


# Create your views here.
@login_required
def mark_completed(request, errand_id):
    errand = get_object_or_404(Errand, id=errand_id)
    
    # Ensure the logged-in user is the assigned runner
    if errand.runner != request.user:
        return HttpResponse("Unauthorized", status=403)
    
    # Update status
    errand.status = "awaiting_approval"
    errand.save()
    return redirect("errand_detail", errand_id=errand.id)

@login_required
def approve_completion(request, errand_id):
    errand = get_object_or_404(Errand, id=errand_id)
    
    # Ensures the logged-in user is the creator
    if errand.user != request.user:
        return HttpResponse("Unauthorized", status=403)
    
    # Mark as completed
    errand.status = "completed"
    errand.save()

    # Trigger payment release
    #release_payment(errand.runner, errand.price)

    return redirect("errand_detail", errand_id=errand.id)
