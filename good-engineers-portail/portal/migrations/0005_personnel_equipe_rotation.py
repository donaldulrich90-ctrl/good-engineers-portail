from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0004_entreprise_logo"),
    ]

    operations = [
        migrations.AddField(
            model_name="entreprise",
            name="matricule_prefix",
            field=models.CharField(blank=True, default="", max_length=20, verbose_name="préfixe matricule"),
        ),
        migrations.AddField(
            model_name="entreprise",
            name="matricule_seq",
            field=models.IntegerField(default=0, verbose_name="compteur matricule"),
        ),
        migrations.AddField(
            model_name="entreprise",
            name="equipes",
            field=models.TextField(blank=True, default="", verbose_name="équipes (une par ligne)"),
        ),
        migrations.AddField(
            model_name="entreprise",
            name="rotations",
            field=models.TextField(blank=True, default="", verbose_name="rotations (une par ligne)"),
        ),
        migrations.AddField(
            model_name="employe",
            name="equipe",
            field=models.CharField(blank=True, default="", max_length=60, verbose_name="équipe"),
        ),
        migrations.AddField(
            model_name="employe",
            name="rotation",
            field=models.CharField(blank=True, default="", max_length=60, verbose_name="rotation"),
        ),
    ]
