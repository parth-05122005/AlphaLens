from django.contrib import admin

from .models import Holding


@admin.register(Holding)
class HoldingAdmin(admin.ModelAdmin):
    list_display = ("symbol", "user", "quantity", "avg_buy_price", "last_price", "last_price_at")
    list_filter = ("sector",)
    search_fields = ("symbol", "name", "user__username")
