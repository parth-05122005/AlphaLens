from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from .models import Holding
from .serializers import HoldingSerializer
from .services import HISTORY_PERIODS, enrich_holding, get_portfolio_summary, get_price_history, invalidate_summary
from .tasks import refresh_prices_task


class HoldingViewSet(viewsets.ModelViewSet):
    serializer_class = HoldingSerializer

    def get_queryset(self):
        return Holding.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        holding = Holding(user=self.request.user, **serializer.validated_data)
        enrich_holding(holding)
        holding.save()
        serializer.instance = holding
        invalidate_summary(self.request.user.id)

    def perform_update(self, serializer):
        serializer.save()
        invalidate_summary(self.request.user.id)

    def perform_destroy(self, instance):
        instance.delete()
        invalidate_summary(self.request.user.id)

    @action(detail=False, methods=["post"], url_path="refresh-prices")
    def refresh_prices(self, request):
        result = refresh_prices_task.delay(request.user.id)
        return Response({"task_id": result.id}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        holding = self.get_object()
        period = request.query_params.get("period", "1mo")
        if period not in HISTORY_PERIODS:
            return Response({"detail": f"period must be one of {', '.join(HISTORY_PERIODS)}"}, status=400)
        try:
            points = get_price_history(holding.symbol, period)
        except Exception:
            return Response({"detail": "Price history is unavailable right now."}, status=502)
        return Response({"symbol": holding.symbol, "period": period, "points": points})


@api_view(["GET"])
def portfolio_summary(request):
    return Response(get_portfolio_summary(request.user))
