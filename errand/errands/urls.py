from django.urls import path
from . import views

urlpatterns = [
    # List errands with optional filters & sorting
    path("api/errands/", views.all_errands, name="all_errands"),

    # Create a new errand
    path("api/errands/create/", views.create_errand, name="create_errand"),

    # Single errand operations
    path("api/errands/<int:errand_id>/", views.single_errand, name="single_errand"),
    path("api/errands/<int:errand_id>/delete/", views.delete_errand, name="delete_errand"),
    path("api/errands/<int:errand_id>/accept/", views.accept_errand, name="accept_errand"),
    path("api/errands/<int:errand_id>/mark_completed/", views.mark_completed, name="mark_completed"),
    path("api/errands/<int:errand_id>/approve_completion/", views.approve_completion, name="approve_completion"),
    path("api/errands/<int:errand_id>/review/", views.review_errand, name="review_errand"),
]
