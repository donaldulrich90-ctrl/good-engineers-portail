from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0006_employe_empreinte"),
    ]

    operations = [
        migrations.AddField(
            model_name="entreprise",
            name="type_mine",
            field=models.CharField(
                blank=True,
                choices=[
                    ("ciel_ouvert", "Mine à ciel ouvert"),
                    ("souterrain", "Mine souterraine"),
                    ("carriere", "Carrière"),
                ],
                default="",
                max_length=20,
                verbose_name="type de mine",
            ),
        ),
    ]
