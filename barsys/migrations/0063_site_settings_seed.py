from django.db import migrations


def create_site_settings(apps, schema_editor):
    # Ensure the SiteSettings singleton row exists. Values are configured manually
    # via the admin Settings page after deployment.
    SiteSettings = apps.get_model("barsys", "SiteSettings")
    SiteSettings.objects.get_or_create(pk=1)


class Migration(migrations.Migration):

    dependencies = [
        ("barsys", "0062_site_settings"),
    ]

    operations = [
        migrations.RunPython(create_site_settings, migrations.RunPython.noop),
    ]
