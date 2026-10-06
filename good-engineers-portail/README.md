# PORTAIL GOOD ENGINEERS

Portail commun qui réunit tes deux plateformes — **Forage** (`DRILLING-GE`,
Node/Express) et **Mine** (`GEMINING-1`, Django) — en une offre modulaire,
**sans réécrire ni fusionner leur code**.

Il apporte quatre choses :

1. **Gestion des entreprises et des modules** — un back-office où chaque client
   a une case « Forage » et une case « Mine ».
2. **Connexion unique (SSO)** — le client se connecte une fois, sur le portail.
3. **Barre de bascule** — passer d'un module à l'autre sans se reconnecter.
4. **Rapport consolidé** — un seul rapport, limité aux modules actifs.

```
                 ┌─────────────────────────────┐
                 │   PORTAIL (ce dépôt, Django) │
                 │  entreprises · modules · SSO │
                 │  bascule · rapport consolidé │
                 └───────┬───────────────┬──────┘
          jeton SSO +    │               │   jeton SSO +
          clé de service │               │   clé de service
                 ┌────────▼─────┐  ┌──────▼────────┐
                 │  FORAGE       │  │  MINE          │
                 │  DRILLING-GE  │  │  GEMINING-1    │
                 │  (inchangé    │  │  (inchangé     │
                 │   + /sso      │  │   + /sso/      │
                 │   + /metrics) │  │   + /metrics/) │
                 └───────────────┘  └───────────────┘
```

Les deux applications restent en ligne et inchangées. On ne leur ajoute que
de petits **adaptateurs** (dossier `adapters/`) : une entrée de connexion
unique, une API de métriques, et l'inclusion de la barre. Leurs anciennes
pages de connexion continuent de servir de secours.

---

## 1. Ce que contient ce dépôt

```
good_engineers_portail/   projet Django (settings, urls, wsgi)
portal/                   app du portail
  models.py               Entreprise (modules + mapping), Profil, journal des jetons
  admin.py                back-office : gérer clients et modules
  views.py                login, dashboard, bascule /go/<module>/, rapport
  sso.py                  émission du jeton de bascule (JWT court, usage unique)
  services.py             appels aux API métriques + propagation d'état
  signals.py              (dé)cocher un module -> (dé)active l'entreprise dans l'app
  hashers.py              bcrypt + compat SHA-256 de la Mine (conversion auto)
  management/commands/importer_mine.py   import des comptes Mine existants
  static/portal/switchbar.js             la barre de bascule (servie aux 2 apps)
  templates/portal/       pages du portail
adapters/forage/          à coller dans DRILLING-GE (Node)
adapters/mine/            à coller dans GEMINING-1 (Django)
Dockerfile, docker-compose.yml, .env.example   déploiement Coolify
```

---

## 2. Déploiement du portail sur Coolify

C'est un **troisième service**, à côté de `gedrilling` et `gemining`.

1. Pousse ce dossier dans un nouveau dépôt GitHub, ex. `PORTAIL-GE`.
2. Dans Coolify : nouvelle ressource → *Dockerfile* → ce dépôt.
3. Domaine : `geportail.duckdns.org` (ou le tien).
4. Volume persistant : monte un volume sur `/app/data` (base SQLite du portail).
5. Variables d'environnement (voir `.env.example`) :

   | Variable | Rôle |
   |---|---|
   | `PORTAIL_SECRET_KEY` | clé Django du portail |
   | `PORTAIL_ALLOWED_HOSTS` | `geportail.duckdns.org` |
   | `PORTAIL_CSRF_TRUSTED_ORIGINS` | `https://geportail.duckdns.org` |
   | `PORTAIL_BASE_URL` | `https://geportail.duckdns.org` |
   | `SSO_SHARED_SECRET` | **secret partagé** avec Forage et Mine |
   | `SERVICE_API_KEY` | **clé de service** partagée avec Forage et Mine |
   | `FORAGE_BASE_URL` | `https://gedrilling.duckdns.org` |
   | `MINE_BASE_URL` | `https://gemining.duckdns.org` |

   Génère les deux secrets une fois : `openssl rand -hex 32` (un pour
   `SSO_SHARED_SECRET`, un pour `SERVICE_API_KEY`), et reporte-les à
   l'identique dans les trois services.

6. Au démarrage, le conteneur fait `migrate` + `collectstatic` tout seul.
7. Crée le compte admin du portail :
   `python manage.py createsuperuser` (via le terminal Coolify du service),
   puis ouvre `/admin/`.

### En local

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export PORTAIL_SECRET_KEY=dev SSO_SHARED_SECRET=dev SERVICE_API_KEY=dev
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

---

## 3. Brancher les adaptateurs

### Forage (`DRILLING-GE`, Node)
Suis `adapters/forage/server-snippet.txt`. En résumé : copier `ge-sso.js` et
`ge-metrics.js` à la racine, les monter dans `server.js` (avant le gardien
d'auth `/api`), coller `switchbar-snippet.html` dans `plateforme-forage.html`,
ajouter `SSO_SHARED_SECRET`, `SERVICE_API_KEY`, `PORTAIL_BASE_URL`.

### Mine (`GEMINING-1`, Django)
Suis `adapters/mine/urls-snippet.txt`. En résumé : copier `ge_sso_views.py` et
`ge_service_views.py` dans `webcore/`, ajouter les routes `/sso/` et
`/api/service/...` (avant `app/<slug>/`), ajouter `/sso` et `/api/service`
aux préfixes publics du middleware, coller `switchbar-snippet.html` dans
`templates/base.html`, ajouter `SSO_SHARED_SECRET` et `SERVICE_API_KEY`,
et `PyJWT>=2.8` dans `requirements.txt`.

---

## 4. Configurer un client

Dans `/admin/` du portail :

1. **Entreprises → Ajouter.** Nom, slug, coche les modules souscrits.
2. **Correspondance avec les applications :**
   - `forage_enterprise_id` = l'`id` de l'entreprise dans la base Forage ;
   - `mine_tenant_id` = l'identifiant de tenant dans la Mine (ex. `default`).
3. **Profils → Ajouter.** Relie un compte au client, et renseigne son
   identité par module (`forage_username`/`forage_role`, `mine_username`/`mine_role`).
   Un couple username/rôle vide = pas d'accès à ce module.

Pour reprendre les comptes existants de la Mine sans que personne ne change
son mot de passe :

```bash
python manage.py importer_mine \
    --fichier /chemin/vers/app_database.json \
    --entreprise-slug sahara --tenant default
```

Les mots de passe SHA-256 de la Mine sont acceptés tels quels puis
**convertis automatiquement en bcrypt** à la première connexion.

---

## 5. Détacher ou rattacher un module

Décoche « module Forage » (ou « Mine ») sur l'entreprise, puis enregistre.
Effet immédiat :

- le module disparaît du tableau de bord et de la barre du client ;
- la bascule SSO vers ce module est refusée ;
- le portail demande en plus à l'application de **désactiver l'entreprise**
  (sécurité pour les accès directs à l'ancienne URL) ;
- **les données restent en base.** Recoche la case : tout revient.

---

## 6. Comment marche la connexion unique (en bref)

1. Le client se connecte sur le portail (bcrypt).
2. Il clique sur un module. Le portail fabrique un **jeton signé** (secret
   partagé), valable **60 s** et **à usage unique** (identifiant `jti`), qui
   porte son identité dans ce module et la liste des modules actifs.
3. Le navigateur est redirigé vers `/sso` (Forage) ou `/sso/` (Mine) avec
   le jeton. L'application le vérifie, ouvre **sa propre session** et affiche
   la barre. Aucune reconnexion.

Le jeton ne sert qu'à franchir la redirection ; il n'est jamais stocké.

---

## 7. Points connus à affiner

- **Anti-rejeu multi-process.** Les jetons déjà utilisés sont gardés en
  mémoire du process (Forage) / dans le cache Django (Mine). Pour plusieurs
  workers, utiliser un cache partagé (Redis) ou une petite table.
- **Carburant Forage.** Le forage ne suit pas encore le carburant en litres
  (le champ est un niveau de cuve en %). La vue croisée additionne donc
  surtout le carburant de la Mine. À brancher quand le forage saisira les litres.
- **Coût d'exploitation Mine.** Le rapport met `cout_total = 0` côté Mine
  (le détail vit dans le module finance). À relier si tu veux le coût mine
  dans la vue croisée.
- **Doublons de modules** (maintenance, stock, RH, facturation présents des
  deux côtés). Pour un client « pack intégral », choisis un module
  propriétaire par domaine et masque l'onglet de l'autre (Forage sait déjà
  masquer des onglets par entreprise via `allowedTabs`).
