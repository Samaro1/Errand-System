from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Errand, Review


@admin.register(Errand)
class ErrandAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "creator",
        "runner",
        "price",
        "status",
        "approved",
        "created_at",
        "has_expired",
    )
    list_filter = ("status", "approved", "created_at")
    search_fields = ("title", "description", "creator__username", "runner__username")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "has_expired")

    fieldsets = (
        ("General Info", {
            "fields": ("title", "description", "price", "duration")
        }),
        ("People", {
            "fields": ("creator", "runner")
        }),
        ("Status & Timestamps", {
            "fields": ("status", "approved", "created_at", "has_expired")
        }),
    )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "runner",
        "reviewer",
        "errand",
        "rating",
        "created_at",
    )
    list_filter = ("rating", "created_at")
    search_fields = (
        "runner__username",
        "reviewer__username",
        "feedback",
    )
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
