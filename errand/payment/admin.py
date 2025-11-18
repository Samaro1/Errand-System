from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
	"""Admin for Payment — list key fields and show provider details read-only."""

	list_display = (
		"reference",
		"errand",
		"payer",
		"amount_paid",
		"status",
		"provider_transfer_id",
		"provider_refund_id",
		"paid_at",
		"created_at",
	)
	list_filter = ("status", "provider")
	search_fields = ("reference", "payer__username", "errand__title")
	readonly_fields = (
		"provider_transfer_id",
		"provider_transfer_status",
		"provider_refund_id",
		"provider_refund_status",
		"recipient_vda",
		"provider_details",
	)

	fieldsets = (
		(None, {"fields": ("reference", "errand", "payer", "amount_expected", "amount_paid", "currency", "status")}),
		("Payment routing", {"fields": ("recipient_vda", "sender_bank", "sender_account_number")}),
		("Provider info", {"fields": ("provider", "provider_transfer_id", "provider_transfer_status", "provider_refund_id", "provider_refund_status", "provider_details")}),
		("Timestamps", {"fields": ("paid_at", "created_at", "updated_at")}),
	)

	def provider_details(self, obj):
		"""Return a small HTML block showing provider-related status for quick inspection."""
		if not obj:
			return ""
		parts = [
			f"<strong>Provider:</strong> {obj.provider}",
			f"<strong>Transfer ID:</strong> {obj.provider_transfer_id or '-'}",
			f"<strong>Transfer status:</strong> {obj.provider_transfer_status or '-'}",
			f"<strong>Refund ID:</strong> {obj.provider_refund_id or '-'}",
			f"<strong>Refund status:</strong> {obj.provider_refund_status or '-'}",
			f"<strong>Recipient VDA:</strong> {obj.recipient_vda or '-'}",
			f"<strong>Refunded:</strong> {obj.refunded}",
		]
		html = "<div style='font-family:monospace'>" + "<br/>".join(parts) + "</div>"
		return mark_safe(html)

	provider_details.short_description = "Provider details"

