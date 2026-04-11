from datetime import date
import os

from django import forms
from django.core.exceptions import ValidationError

from .models import Thesis


class ThesisUploadForm(forms.ModelForm):
    author_names = forms.CharField(help_text="Comma-separated author names")
    keyword_names = forms.CharField(required=False, help_text="Comma-separated keywords")

    class Meta:
        model = Thesis
        fields = ["title", "abstract", "pdf_file", "course", "year", "preview_page"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.update(
                {
                    "class": "mt-1 w-full rounded-2xl border border-cyan-400/20 bg-slate-950/60 px-4 py-3 text-sm text-white placeholder:text-slate-500 focus:border-cyan-300 focus:outline-none",
                }
            )

            if name == "pdf_file":
                field.widget.attrs.update({"accept": ".pdf,application/pdf", "required": "required"})

            if name in {"year", "preview_page"}:
                field.widget.attrs.update({"type": "number", "inputmode": "numeric", "step": "1"})

        self.fields["year"].widget.attrs.update({"min": "1900", "max": str(date.today().year + 1)})
        self.fields["preview_page"].widget.attrs.update({"min": "1"})

    def clean_pdf_file(self):
        pdf_file = self.cleaned_data.get("pdf_file")
        if not pdf_file:
            raise ValidationError("PDF file is required.")

        extension = os.path.splitext(pdf_file.name)[1].lower()
        if extension != ".pdf":
            raise ValidationError("Only PDF files are allowed.")

        content_type = getattr(pdf_file, "content_type", "") or ""
        if content_type and content_type not in {"application/pdf", "application/x-pdf"}:
            raise ValidationError("Only PDF files are allowed.")

        return pdf_file

    def clean_year(self):
        year = self.cleaned_data.get("year")
        current_year = date.today().year
        if year is None:
            raise ValidationError("Year is required.")
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
