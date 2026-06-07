from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("barsys", "0061_easyverein_contact_details_url"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteSettings",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("easyverein_api_token", models.CharField(blank=True, default="", max_length=512)),
                ("easyverein_bank_account_id", models.IntegerField(default=0)),
            ],
            options={
                "verbose_name": "Site settings",
            },
        ),
    ]
