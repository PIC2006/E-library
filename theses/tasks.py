from celery import shared_task
from django.core.files.base import ContentFile
import fitz
from pypdf import PdfReader

from .models import Thesis, ThesisPreview


def extract_thesis_text(thesis, max_pages=8):
    thesis.pdf_file.open("rb")
    reader = PdfReader(thesis.pdf_file)
    extracted_text = []
    for page in reader.pages[:max_pages]:
        extracted_text.append(page.extract_text() or "")
    thesis.search_document = "\n".join(extracted_text).strip()
    thesis.save(update_fields=["search_document", "updated_at"])
    return len(reader.pages)


def build_thesis_previews(thesis, max_pages=2):
    try:
        doc = fitz.open(thesis.pdf_file.path)
    except Exception:
        thesis.pdf_file.open("rb")
        pdf_bytes = thesis.pdf_file.read()
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
