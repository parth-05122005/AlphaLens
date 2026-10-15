from django.conf import settings
from django.db import models


class Holding(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="holdings")
    symbol = models.CharField(max_length=32)
    name = models.CharField(max_length=200, blank=True)
    sector = models.CharField(max_length=100, blank=True, null=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    avg_buy_price = models.DecimalField(max_digits=14, decimal_places=2)
    last_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    last_price_at = models.DateTimeField(null=True, blank=True)
    news_refreshed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["symbol"]
        constraints = [models.UniqueConstraint(fields=["user", "symbol"], name="unique_holding_per_user")]

    def __str__(self):
        return f"{self.symbol} ({self.user})"
