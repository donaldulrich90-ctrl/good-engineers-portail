from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0002_employe_pointage"),
    ]

    operations = [
        migrations.CreateModel(
            name="RapportCommentaire",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("start", models.DateField()),
                ("end", models.DateField()),
                ("texte", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("entreprise", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rapport_commentaires", to="portal.entreprise")),
            ],
            options={
                "verbose_name": "commentaire de rapport",
                "verbose_name_plural": "commentaires de rapport",
            },
        ),
        migrations.AddConstraint(
            model_name="rapportcommentaire",
            constraint=models.UniqueConstraint(fields=("entreprise", "start", "end"), name="rapportcommentaire_unique_periode"),
        ),
    ]
