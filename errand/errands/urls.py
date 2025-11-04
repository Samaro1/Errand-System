from django.urls import path
from . import views

urlpatterns=[
    path("", views.all_errands, name="allerrands"),
    path("create/", views.create_errand, name= "errandcreate"),
    path("<int:id>/delete_errand/", views.delete_errand, name= "erranddelete"),
    path("<int:id>/", views.single_errand, name="singleerrand"),
    path("<int:id>/accept/", views.accept_errand, name= "accept_errand"),
    path("<int:id>/review/", views.review_errand, name= "errand_review")
]