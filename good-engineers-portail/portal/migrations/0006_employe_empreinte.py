from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0005_personnel_equipe_rotation"),
    ]

    operations = [
        migrations.AddField(
            model_name="employe",
            name="empreinte_template",
            field=models.TextField(blank=True, default="", verbose_name="gabarit d'empreinte (chiffré)"),
        ),
        migrations.AddField(
            model_name="employe",
            name="empreinte_doigt",
            field=models.CharField(blank=True, default="", max_length=30, verbose_name="doigt enrôlé"),
        ),
        migrations.AddField(
            model_name="employe",
            name="empreinte_enrolee",
            field=models.BooleanField(default=False, verbose_name="empreinte enrôlée"),
        ),
    ]
