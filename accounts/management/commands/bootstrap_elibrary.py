from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from theses.models import Course, Keyword


class Command(BaseCommand):
    help = "Create a bootstrap superuser and seed baseline repository data."

    def add_arguments(self, parser):
        parser.add_argument("--create-superuser", action="store_true", help="Create or update the bootstrap superuser.")
        parser.add_argument("--seed", action="store_true", help="Seed sample courses and keywords.")
        parser.add_argument("--seed-users", action="store_true", help="Seed demo student and guest users.")
        parser.add_argument("--username", default="admin")
        parser.add_argument("--email", default="admin@elibrary.local")
        parser.add_argument("--password", default="Admin123!ChangeMe")

    def handle(self, *args, **options):
        user_model = get_user_model()
        created_items = []

        if options["create_superuser"]:
            user, created = user_model.objects.get_or_create(
                username=options["username"],
                defaults={
                    "email": options["email"],
                    "is_staff": True,
                    "is_superuser": True,
                    "role": user_model.Role.ADMIN,
                },
            )
            user.email = options["email"]
            user.is_staff = True
            user.is_superuser = True
            user.role = user_model.Role.ADMIN
            user.set_password(options["password"])
            user.save()
            created_items.append(f"superuser:{user.username}:{'created' if created else 'updated'}")

        if options["seed"]:
            courses = [
                {"name": "MAED", "code": "MAED", "department": "Graduate School"},
                {"name": "PHD", "code": "PHD", "department": "Graduate School"},
            ]
            keywords = ["research", "system", "library", "analytics", "thesis", "education"]

            for payload in courses:
                course, created = Course.objects.get_or_create(name=payload["name"], defaults=payload)
                if not created:
                    Course.objects.filter(pk=course.pk).update(code=payload["code"], department=payload["department"])
                created_items.append(f"course:{course.name}")

            for keyword_name in keywords:
                Keyword.objects.get_or_create(name=keyword_name)
                created_items.append(f"keyword:{keyword_name}")

        if options["seed_users"]:
            demo_users = [
                {"username": "student1", "email": "student1@elibrary.local", "role": user_model.Role.STUDENT},
                {"username": "guest1", "email": "guest1@elibrary.local", "role": user_model.Role.GUEST},
            ]
            for payload in demo_users:
                user, created = user_model.objects.get_or_create(username=payload["username"], defaults=payload)
                if not created:
                    user.email = payload["email"]
                    user.role = payload["role"]
                user.set_password(options["password"])
                user.save()
                created_items.append(f"user:{user.username}")

        if created_items:
            self.stdout.write(self.style.SUCCESS("Bootstrap completed: " + ", ".join(created_items)))
        else:
            self.stdout.write(self.style.WARNING("Nothing to bootstrap. Use --create-superuser and/or --seed."))