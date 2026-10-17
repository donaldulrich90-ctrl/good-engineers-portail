from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0003_rapportcommentaire"),
    ]

    operations = [
        migrations.AddField(
            model_name="entreprise",
            name="logo",
            field=models.TextField(blank=True, default="", verbose_name="logo (data URI)"),
        ),
    ]
