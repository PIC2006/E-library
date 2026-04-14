from django.db import models


class LibrarySource(models.Model):
    class Category(models.TextChoices):
        FREE_ELIBRARY = "free_elibrary", "Free E-Library"
        GDRIVE = "gdrive", "G-Drive"
        OTHER = "other", "Other"

    label = models.CharField(max_length=120)
    url = models.URLField()
    category = models.CharField(max_length=24, choices=Category.choices, default=Category.OTHER, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["sort_order", "label"]

    def __str__(self):
        return self.label