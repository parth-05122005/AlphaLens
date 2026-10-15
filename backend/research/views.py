import logging

from django.conf import settings
from django.db.models import Avg, Count, Q
from google.genai import errors as genai_errors
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, throttle_classes
from rest_framework.generics import ListAPIView
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from core.llm import LLMError
from core.retry import NETWORK_ERRORS
from portfolio.models import Holding

from .alerts import get_alerts
from .models import Chunk, Document, QueryLog
from .rag import answer_question
from .serializers import AskSerializer, DocumentDetailSerializer, DocumentSerializer, QueryLogSerializer
from .tasks import ingest_document_task

logger = logging.getLogger(__name__)

MAX_PDF_BYTES = 10 * 1024 * 1024


def extract_pdf_text(file) -> str:
    reader = PdfReader(file)
    return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()


class DocumentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    def get_queryset(self):
        qs = Document.objects.filter(user=self.request.user).select_related("holding")
        params = self.request.query_params
        if holding := params.get("holding"):
            qs = qs.filter(holding_id=holding)
        if source_type := params.get("source_type"):
            qs = qs.filter(source_type=source_type)
        if doc_status := params.get("status"):
            qs = qs.filter(status__in=doc_status.split(","))
        return qs

    def get_serializer_class(self):
        return DocumentDetailSerializer if self.action == "retrieve" else DocumentSerializer

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser])
    def upload(self, request):
        file = request.FILES.get("file")
        if file is None:
            return Response({"file": ["Attach a PDF file."]}, status=400)
        if file.size > MAX_PDF_BYTES:
            return Response({"file": ["PDF must be 10 MB or smaller."]}, status=400)
        if not file.name.lower().endswith(".pdf"):
            return Response({"file": ["Only PDF files are supported."]}, status=400)

        holding = None
        if holding_id := request.data.get("holding"):
            holding = Holding.objects.filter(pk=holding_id, user=request.user).first()
            if holding is None:
                return Response({"holding": ["Unknown holding."]}, status=400)

        try:
            text = extract_pdf_text(file)
        except (PdfReadError, ValueError, OSError):
            logger.info("Unreadable PDF upload: %s", file.name, exc_info=True)
            return Response({"file": ["Could not read this PDF."]}, status=400)
        if not text:
            return Response({"file": ["No extractable text found (scanned PDFs aren't supported)."]}, status=400)

        # Only the extracted text is stored: Render's disk is ephemeral and the worker may run elsewhere.
        document = Document.objects.create(
            user=request.user,
            holding=holding,
            source_type=Document.SourceType.PDF,
            title=file.name.rsplit(".", 1)[0][:500],
            content=text,
        )
        result = ingest_document_task.delay(document.id)
        document.refresh_from_db()
        return Response(
            {**DocumentSerializer(document).data, "task_id": result.id},
            status=status.HTTP_201_CREATED,
        )


class AskThrottle(UserRateThrottle):
    """Per-user limit on /ask/. DRF throttles store their history in the default cache (Redis)."""

    scope = "ask"

    def get_rate(self):
        return settings.ASK_RATE_LIMIT


@api_view(["POST"])
@throttle_classes([AskThrottle])
def ask(request):
    serializer = AskSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    question = serializer.validated_data["question"]
    requested = serializer.validated_data["holding_ids"]
    holding_ids = list(Holding.objects.filter(user=request.user, pk__in=requested).values_list("pk", flat=True))
    if len(holding_ids) != len(set(requested)):
        return Response({"holding_ids": ["Unknown holding."]}, status=400)
    try:
        result = answer_question(request.user, question, holding_ids)
    except NETWORK_ERRORS + (LLMError, genai_errors.APIError):
        logger.warning("Ask failed", exc_info=True)
        return Response({"detail": "The AI service is unavailable right now. Please try again shortly."}, status=503)
    return Response(result)


class AskHistoryView(ListAPIView):
    serializer_class = QueryLogSerializer

    def get_queryset(self):
        return QueryLog.objects.filter(user=self.request.user)


@api_view(["GET"])
def stats(request):
    logs = QueryLog.objects.filter(user=request.user)
    agg = logs.aggregate(
        total=Count("id"),
        hits=Count("id", filter=Q(cache_hit=True)),
        cached_avg=Avg("latency_ms", filter=Q(cache_hit=True)),
        uncached_avg=Avg("latency_ms", filter=Q(cache_hit=False)),
    )
    total = agg["total"]
    return Response(
        {
            "total_queries": total,
            "cache_hit_rate": round(agg["hits"] / total, 3) if total else 0.0,
            "avg_latency_ms_cached": round(agg["cached_avg"]) if agg["cached_avg"] is not None else None,
            "avg_latency_ms_uncached": round(agg["uncached_avg"]) if agg["uncached_avg"] is not None else None,
            "documents_count": Document.objects.filter(user=request.user).count(),
            "chunks_count": Chunk.objects.filter(document__user=request.user).count(),
        }
    )


@api_view(["GET"])
def alerts(request):
    return Response(get_alerts(request.user))
