from celery import shared_task
import io
import os
import urllib.request

from django.core.files.base import ContentFile
import fitz
from pypdf import PdfReader

from .models import Thesis, ThesisPreview


def _load_pdf_bytes(thesis):
    try:
        file_path = thesis.pdf_file.path
    except (NotImplementedError, ValueError, OSError):
        file_path = None

    if file_path and os.path.exists(file_path):
        with open(file_path, "rb") as handle:
            return handle.read()

    file_url = thesis.pdf_file.url
    with urllib.request.urlopen(file_url) as remote_file:
        return remote_file.read()


def extract_thesis_text(thesis, max_pages=8):
    pdf_bytes = _load_pdf_bytes(thesis)
    reader = PdfReader(io.BytesIO(pdf_bytes))
    extracted_text = []
    for page in reader.pages[:max_pages]:
        extracted_text.append(page.extract_text() or "")
    thesis.search_document = "\n".join(extracted_text).strip()
    thesis.save(update_fields=["search_document", "updated_at"])
    return len(reader.pages)


def build_thesis_previews(thesis, max_pages=2):
    pdf_bytes = _load_pdf_bytes(thesis)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    ThesisPreview.objects.filter(thesis=thesis).delete()
    previews = []

    for index in range(min(max_pages, len(doc))):
        page = doc.load_page(index)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False)
        image_name = f"{thesis.id}_page_{index + 1}.png"
        preview = ThesisPreview(thesis=thesis, page_number=index + 1)
        preview.preview_file.save(image_name, ContentFile(pixmap.tobytes("png")), save=False)
        previews.append(preview)

    if previews:
        ThesisPreview.objects.bulk_create(previews)

    return len(previews)


@shared_task
def process_thesis_upload(thesis_id):
    thesis = Thesis.objects.select_related("course").prefetch_related("authors", "keywords").get(pk=thesis_id)
    page_count = extract_thesis_text(thesis)
    preview_count = build_thesis_previews(thesis)
    return {"thesis_id": str(thesis.id), "pages": page_count, "preview_count": preview_count}


@shared_task
def generate_thesis_previews(thesis_id, max_pages=3):
    thesis = Thesis.objects.get(pk=thesis_id)
    preview_count = build_thesis_previews(thesis, max_pages=max_pages)
    return {"thesis_id": str(thesis.id), "preview_count": preview_count}
