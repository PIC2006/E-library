from datetime import date
import os
import hashlib

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from .models import Thesis


class ThesisUploadForm(forms.ModelForm):
    author_names = forms.CharField(required=False, help_text="Comma-separated author names")
    keyword_names = forms.CharField(required=False, help_text="Comma-separated keywords")

    class Meta:
        model = Thesis
        fields = ["title", "abstract", "pdf_file", "course", "year", "preview_page"]

    @staticmethod
    def _cloudinary_upload_limit_mb():
        if not getattr(settings, "USE_CLOUDINARY", False):
            return 0.0
        cloudinary_limit = float(getattr(settings, "PDF_CLOUDINARY_MAX_MB", 0) or 0)
        if cloudinary_limit > 0:
            return cloudinary_limit
        return float(getattr(settings, "PDF_UPLOAD_MAX_MB", 0) or 0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            field.widget.attrs.update(
                {
                    "class": "mt-1 w-full rounded-2xl border border-cyan-400/20 bg-slate-950/60 px-4 py-3 text-sm text-white placeholder:text-slate-500 focus:border-cyan-300 focus:outline-none",
                }
            )

            if name == "pdf_file":
                # Make PDF optional in edit mode
                is_editing = bool(self.instance and not self.instance._state.adding)
                if not is_editing:
                    field.widget.attrs.update({"accept": ".pdf,application/pdf", "required": "required"})
                    field.required = True
                else:
                    field.widget.attrs.update({"accept": ".pdf,application/pdf"})
                    field.required = False

                max_upload_mb = float(getattr(settings, "PDF_UPLOAD_MAX_MB", 0) or 0)
                if max_upload_mb > 0:
                    field.help_text = f"Maximum file size: {max_upload_mb:g} MB"

                cloudinary_limit_mb = self._cloudinary_upload_limit_mb()
                if cloudinary_limit_mb > 0:
                    field.widget.attrs.update(
                        {
                            "data-max-size-mb": f"{cloudinary_limit_mb:g}",
                            "data-max-size-provider": "cloudinary",
                        }
                    )
                    if max_upload_mb <= 0:
                        field.help_text = f"Cloudinary upload limit: {cloudinary_limit_mb:g} MB"

            if name in {"year", "preview_page"}:
                field.widget.attrs.update({"type": "number", "inputmode": "numeric", "step": "1"})

        self.fields["year"].widget.attrs.update({"min": "1900", "max": str(date.today().year + 1)})
        self.fields["year"].required = False
        self.fields["preview_page"].widget.attrs.update({"min": "1"})

    def clean_pdf_file(self):
        pdf_file = self.cleaned_data.get("pdf_file")
        
        # Allow empty PDF file in edit mode (when editing existing thesis)
        if not pdf_file and self.instance and self.instance.pk:
            return pdf_file
        
        if not pdf_file:
            raise ValidationError("PDF file is required.")

        extension = os.path.splitext(pdf_file.name)[1].lower()
        if extension != ".pdf":
            raise ValidationError("Only PDF files are allowed.")

        content_type = getattr(pdf_file, "content_type", "") or ""
        if content_type and content_type not in {"application/pdf", "application/x-pdf"}:
            raise ValidationError("Only PDF files are allowed.")

        max_upload_mb = float(getattr(settings, "PDF_UPLOAD_MAX_MB", 0) or 0)
        if max_upload_mb > 0:
            max_upload_bytes = int(max_upload_mb * 1024 * 1024)
            file_size = getattr(pdf_file, "size", None)
            if file_size is not None and file_size > max_upload_bytes:
                raise ValidationError(
                    f"PDF is too large ({file_size / (1024 * 1024):.2f} MB). Maximum allowed is {max_upload_mb:g} MB."
                )

        cloudinary_limit_mb = self._cloudinary_upload_limit_mb()
        if cloudinary_limit_mb > 0:
            cloudinary_limit_bytes = int(cloudinary_limit_mb * 1024 * 1024)
            file_size = getattr(pdf_file, "size", None)
            if file_size is not None and file_size > cloudinary_limit_bytes:
                raise ValidationError(
                    f"PDF is too large for Cloudinary ({file_size / (1024 * 1024):.2f} MB). "
                    f"Compress it first, then upload again (max {cloudinary_limit_mb:g} MB)."
                )

        # Calculate file hash and check for duplicates
        pdf_file.seek(0)
        file_hash = hashlib.sha256(pdf_file.read()).hexdigest()
        pdf_file.seek(0)
        self._uploaded_file_hash = file_hash

        # Check if this file hash already exists (skip if editing the same thesis)
        existing = Thesis.objects.filter(file_hash=file_hash).exclude(pk=self.instance.pk if self.instance.pk else None)
        if existing.exists():
            raise ValidationError("This PDF file has already been uploaded. Please upload a different file.")

        return pdf_file

    def clean(self):
        cleaned_data = super().clean()
        is_editing = bool(self.instance and not self.instance._state.adding)
        if not is_editing and not cleaned_data.get("pdf_file"):
            self.add_error("pdf_file", "PDF file is required.")
        return cleaned_data

    def clean_year(self):
        year = self.cleaned_data.get("year")
        current_year = date.today().year
        if year is not None:
            if year < 1900 or year > current_year + 1:
                raise ValidationError("Enter a valid year.")
        return year

    def clean_preview_page(self):
        preview_page = self.cleaned_data.get("preview_page")
        if preview_page is None:
            raise ValidationError("Preview page is required.")
        if preview_page < 1:
            raise ValidationError("Preview page must be a positive number.")
        return preview_page
