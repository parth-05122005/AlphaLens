import logging

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from portfolio.models import Holding

from .models import Document
from .serializers import DocumentDetailSerializer, DocumentSerializer
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
