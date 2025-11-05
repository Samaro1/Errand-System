from django.urls import path
from . import views

urlpatterns = [
    # List all or create new one
    path("", views.all_errands, name="all_errands"),      
    path("create/", views.create_errand, name="create_errand"), 

    # Single errand operations
    path("<int:errand_id>/", views.single_errand, name="single_errand"),  # GET one
    path("<int:errand_id>/delete/", views.delete_errand, name="delete_errand"),
    path("<int:errand_id>/accept/", views.accept_errand, name="accept_errand"), 
    path("<int:errand_id>/review/", views.review_errand, name="review_errand"),

    # Status update endpoints
    path("<int:errand_id>/mark_completed/", views.mark_completed, name="mark_completed"),
    path("<int:errand_id>/approve_completion/", views.approve_completion, name="approve_completion"),
]
