from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...models import ApprovalLog, Author, Course, Keyword, Thesis
from ...tasks import generate_thesis_previews


class Command(BaseCommand):
    help = "Seed a sample public thesis using the workspace PDF and generate previews immediately."

    def add_arguments(self, parser):
        parser.add_argument("--pdf", default="GINALYN B. MAGSUMBOL (1).pdf", help="Path to the source PDF file.")
        parser.add_argument("--title", default="Digital Repository Access and Thesis Preservation")
        parser.add_argument("--author", default="Ginalyn B. Magsumbol")
        parser.add_argument("--course", default="MAED")
        parser.add_argument("--year", type=int, default=2026)
        parser.add_argument("--keywords", default="repository,search,library,pdf,analytics")

    def handle(self, *args, **options):
        pdf_path = Path(options["pdf"])
        if not pdf_path.is_absolute():
            pdf_path = Path.cwd() / pdf_path
        if not pdf_path.exists():
            raise CommandError(f"PDF file not found: {pdf_path}")

        user_model = get_user_model()
        owner = user_model.objects.filter(is_superuser=True).order_by("id").first()
        if owner is None:
            owner = user_model.objects.create_superuser(
                username="admin",
                email="admin@elibrary.local",
                password="Admin123!ChangeMe",
            )
            owner.role = user_model.Role.ADMIN
            owner.save(update_fields=["role"])

        course, _ = Course.objects.get_or_create(
            name=options["course"],
            defaults={"code": "DEMO", "department": "Demo Department"},
        )
        author, _ = Author.objects.get_or_create(full_name=options["author"])
        keyword_objects = [
            Keyword.objects.get_or_create(name=keyword.strip().lower())[0]
            for keyword in options["keywords"].split(",")
            if keyword.strip()
        ]

        with transaction.atomic():
            thesis, created = Thesis.objects.get_or_create(
                title=options["title"],
                defaults={
                    "abstract": "A demonstration thesis record used to validate uploads, preview generation, and search indexing.",
                    "course": course,
                    "year": options["year"],
                    "uploaded_by": owner,
                    "approved_by": owner,
                    "status": Thesis.Status.APPROVED,
                    "is_public": True,
                },
            )

            thesis.abstract = "A demonstration thesis record used to validate uploads, preview generation, and search indexing."
            thesis.course = course
            thesis.year = options["year"]
            thesis.uploaded_by = owner
            thesis.approved_by = owner
            thesis.status = Thesis.Status.APPROVED
            thesis.is_public = True
            thesis.save()

            with pdf_path.open("rb") as source_file:
                thesis.pdf_file.save(pdf_path.name, File(source_file), save=True)

            thesis.authors.set([author])
            thesis.keywords.set(keyword_objects)
            ApprovalLog.objects.update_or_create(
                thesis=thesis,
                admin=owner,
                action=ApprovalLog.Action.APPROVED,
                defaults={"note": "Bootstrap approval for the sample thesis."},
            )

        self.stdout.write(self.style.SUCCESS(f"Sample thesis {'created' if created else 'updated'}: {thesis.title}"))

        from pypdf import PdfReader

        thesis.refresh_from_db()
        thesis.pdf_file.open("rb")
        reader = PdfReader(thesis.pdf_file)
        thesis.search_document = "\n".join((page.extract_text() or "") for page in reader.pages[:20]).strip()
        thesis.save(update_fields=["search_document", "updated_at"])
        generate_thesis_previews.run(str(thesis.pk))

        self.stdout.write(self.style.SUCCESS(f"Preview pages generated for thesis {thesis.pk}"))
