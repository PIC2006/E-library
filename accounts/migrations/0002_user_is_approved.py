from django.db import migrations, models


def approve_existing_users(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.all().update(is_approved=True)


def unapprove_existing_users(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.all().update(is_approved=False)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_approved",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(approve_existing_users, unapprove_existing_users),
    ]
