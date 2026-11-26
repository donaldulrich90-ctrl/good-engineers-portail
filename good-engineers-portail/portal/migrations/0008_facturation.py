from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0007_entreprise_type_mine"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModuleTarif",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(choices=[("forage", "Forage"), ("mine", "Mine")], max_length=20, unique=True, verbose_name="module")),
                ("libelle", models.CharField(max_length=80, verbose_name="libellé")),
                ("prix_mensuel", models.DecimalField(decimal_places=0, default=0, max_digits=14, verbose_name="prix mensuel")),
                ("devise", models.CharField(default="XOF", max_length=8, verbose_name="devise")),
                ("actif", models.BooleanField(default=True, verbose_name="actif")),
            ],
            options={"verbose_name": "tarif de module", "verbose_name_plural": "tarifs de modules", "ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="Facture",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero", models.CharField(max_length=30, unique=True, verbose_name="numéro")),
                ("periode", models.CharField(max_length=7, verbose_name="période (YYYY-MM)")),
                ("date_emission", models.DateField(verbose_name="date d'émission")),
                ("echeance", models.DateField(blank=True, null=True, verbose_name="échéance")),
                ("devise", models.CharField(default="XOF", max_length=8, verbose_name="devise")),
                ("statut", models.CharField(choices=[("brouillon", "Brouillon"), ("emise", "Émise"), ("partielle", "Partiellement payée"), ("payee", "Payée"), ("impayee", "Impayée")], default="emise", max_length=12, verbose_name="statut")),
                ("note", models.TextField(blank=True, default="", verbose_name="note")),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("entreprise", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="factures", to="portal.entreprise")),
            ],
            options={"verbose_name": "facture", "verbose_name_plural": "factures", "ordering": ["-periode", "-cree_le"]},
        ),
        migrations.CreateModel(
            name="FactureLigne",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("libelle", models.CharField(max_length=120, verbose_name="libellé")),
                ("module_code", models.CharField(blank=True, default="", max_length=20, verbose_name="module")),
                ("montant", models.DecimalField(decimal_places=0, default=0, max_digits=14, verbose_name="montant")),
                ("facture", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lignes", to="portal.facture")),
            ],
        ),
        migrations.CreateModel(
            name="Paiement",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(verbose_name="date")),
                ("montant", models.DecimalField(decimal_places=0, default=0, max_digits=14, verbose_name="montant")),
                ("moyen", models.CharField(choices=[("especes", "Espèces"), ("virement", "Virement"), ("mobile", "Mobile money"), ("cheque", "Chèque"), ("autre", "Autre")], default="virement", max_length=12, verbose_name="moyen")),
                ("reference", models.CharField(blank=True, default="", max_length=80, verbose_name="référence")),
                ("note", models.CharField(blank=True, default="", max_length=200, verbose_name="note")),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("facture", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="paiements", to="portal.facture")),
            ],
            options={"verbose_name": "paiement", "verbose_name_plural": "paiements", "ordering": ["-date", "-cree_le"]},
        ),
    ]
