from rest_framework import serializers

from .models import Holding
from .services import holding_metrics, normalize_symbol


class HoldingSerializer(serializers.ModelSerializer):
    invested = serializers.SerializerMethodField()
    value = serializers.SerializerMethodField()
    pnl = serializers.SerializerMethodField()
    pnl_pct = serializers.SerializerMethodField()

    class Meta:
        model = Holding
        fields = [
            "id", "symbol", "name", "sector", "quantity", "avg_buy_price",
            "last_price", "last_price_at", "news_refreshed_at", "created_at",
            "invested", "value", "pnl", "pnl_pct",
        ]
        read_only_fields = ["last_price", "last_price_at", "news_refreshed_at", "created_at"]
        extra_kwargs = {"name": {"required": False}, "sector": {"required": False}}

    def validate_symbol(self, value):
        symbol = normalize_symbol(value)
        user = self.context["request"].user
        qs = Holding.objects.filter(user=user, symbol=symbol)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(f"You already hold {symbol}.")
        return symbol

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0.")
        return value

    def validate_avg_buy_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Average buy price must be greater than 0.")
        return value

    def _metric(self, obj, key):
        return holding_metrics(obj)[key]

    def get_invested(self, obj):
        return self._metric(obj, "invested")

    def get_value(self, obj):
        return self._metric(obj, "value")

    def get_pnl(self, obj):
        return self._metric(obj, "pnl")

    def get_pnl_pct(self, obj):
        return self._metric(obj, "pnl_pct")
