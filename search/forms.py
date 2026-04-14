from django import forms

from .models import LibrarySource


class LibrarySourceForm(forms.ModelForm):
    class Meta:
        model = LibrarySource
        fields = ["label", "url", "category", "sort_order"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "mt-1 w-full rounded-2xl border border-cyan-400/20 bg-slate-950/60 px-4 py-3 text-sm text-white placeholder:text-slate-500 focus:border-cyan-300 focus:outline-none",
                }
            )

        self.fields["sort_order"].required = False
        self.fields["sort_order"].widget.attrs.update({"type": "number", "min": "0", "step": "1"})