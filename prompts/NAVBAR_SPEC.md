# NAVBAR_SPEC — Barre de Navigation Intelligente VOC Platform

## Contexte

La plateforme VOC (Flask + SQL Server + Bootstrap) possède déjà :
- Un module Auth complet (JWT via cookie + localStorage)
- Un `base.html` avec une sidebar fixe gauche (240px) en dark theme
- Un blueprint `vtracker` avec les routes `/vtracker/`, `/vtracker/list`, `/vtracker/detail/<id>`
- 20 scopes en DB répartis en 3 catégories : `applicatif`, `systeme`, `systeme_app`
- Un modèle `User` avec `role` (`admin` | `user`) et `scope_id`
- Le JWT contient les claims : `username`, `role`, `scope_id`, `scope`, `is_admin`
- L'utilisateur est disponible côté JS dans `localStorage.getItem('voc_user')` (JSON)

**Scopes en base (voc_seed_v2.sql) :**
```
category='systeme'     → IDs 15,16,17,18,19
  15 - Datacenter Team
  16 - Linux Team
  17 - Windows Team
  18 - Network Team
  19 - Middleware & Tools

category='applicatif'  → IDs 1..14
   1 - Digital Workspace
   2 - Cyber Security
   3 - ITAM
   4 - IT Core Banking & Life Insurance
   5 - IT Data & Corporate Functions
   6 - IT Financial Control & PMO
   7 - IT Governance
   8 - IT ICB
   9 - IT Markets
  10 - IT Operations & Infrastructures
  11 - IT Payment & Compliance
  12 - IT PWM & IFA
  13 - Software Development Factory
  14 - Other

category='systeme_app' → ID 20
  20 - IT Operations & Infrastructures Ops
```

---

## Prompt d'implémentation

Implémente une barre de navigation latérale intelligente pour la plateforme VOC.
La sidebar adapte son contenu selon le rôle de l'utilisateur connecté (`admin` vs `user`).
Après connexion :
- Un **admin** est redirigé vers `/overview/`
- Un **user** est redirigé vers `/vtracker/` (scope filtré automatiquement)

---

## Fonctionnalités à implémenter

---

### 1. Redirection post-login intelligente

**Fichier :** `app/templates/auth/login.html`

Dans le bloc `if (resp.ok)` du `fetch('/api/auth/login')` :

```
si data.user.role === 'admin'  →  window.location.href = '/overview/'
sinon                          →  window.location.href = '/vtracker/'
```

---

### 2. Sidebar intelligente — Structure selon le rôle

**Fichier :** `app/templates/shared/base.html`

La sidebar est construite en JavaScript via `vocUser` (localStorage).
Les scopes sont chargés dynamiquement depuis un endpoint API `/api/scopes` au montage de la sidebar.

#### Structure complète pour ADMIN

```
┌─────────────────────────────────┐
│  🛡 VOC Platform                │  ← brand → /overview/
├─────────────────────────────────┤
│  OVERVIEW                       │
│    ⬚  Overview                  │  → /overview/
│                                 │
│  MONITORING                     │
│  ▼ V-Tracker             [↓]   │  ← collapsible principal
│    │                            │
│    ├─ ▶ Systeme          [↓]   │  ← collapsible niveau 2
│    │     ├── Datacenter Team    │  → /vtracker/list?scope_id=15
│    │     ├── Linux Team         │  → /vtracker/list?scope_id=16
│    │     ├── Windows Team       │  → /vtracker/list?scope_id=17
│    │     ├── Network Team       │  → /vtracker/list?scope_id=18
│    │     └── Middleware & Tools │  → /vtracker/list?scope_id=19
│    │                            │
│    ├─ ▶ Applicatifs      [↓]   │  ← collapsible niveau 2
│    │     ├── Digital Workspace  │  → /vtracker/list?scope_id=1
│    │     ├── Cyber Security     │  → /vtracker/list?scope_id=2
│    │     ├── ITAM               │  → /vtracker/list?scope_id=3
│    │     └── ... (14 scopes)    │
│    │                            │
│    └─ ▶ Sys+App           [↓]  │  ← collapsible niveau 2
│          └── IT Ops & Infra Ops │  → /vtracker/list?scope_id=20
│                                 │
│  ASSETS                         │  ← section séparée
│    🖥  Assets                   │  → /assets/
│                                 │
│  USERS                          │  ← section séparée
│    👥  Users                    │  → /users/
│                                 │
│  INPUT                          │
│  ▼ V-Hub                 [↓]   │  ← collapsible (existant)
│      📡  CTI                    │  → /vhub/cti
│      📈  BitSight               │  → /vhub/bitsight
│      🎯  Red Team               │  → /vhub/redteam
│                                 │
│  ANALYTICS                      │
│      📊  Reporting              │  → /reporting/
│                                 │
│  SYSTEM                         │  ← admin only
│      ⚙   Admin Panel            │  → /admin/
├─────────────────────────────────┤
│  username                       │
│  scope_name  [admin]      [→]   │
└─────────────────────────────────┘
```

#### Structure pour USER (non-admin)

```
┌─────────────────────────────────┐
│  🛡 VOC Platform                │  ← brand → /vtracker/
├─────────────────────────────────┤
│  MONITORING                     │
│    ⬚  V-Tracker                 │  → /vtracker/list  (scope_id auto depuis JWT)
│                                 │
│  INPUT                          │
│  ▼ V-Hub                 [↓]   │
│      📡  CTI                    │
│      📈  BitSight               │
│      🎯  Red Team               │
│                                 │
│  ANALYTICS                      │
│      📊  Reporting              │  → /reporting/
├─────────────────────────────────┤
│  username                       │
│  scope_name               [→]   │
└─────────────────────────────────┘
```

**Règles d'activation (classe CSS `active`) :**
- Overview : `pathname === '/overview/'`
- Scope individuel : `URLSearchParams.get('scope_id') === '<id>'`
- Systeme parent : actif si `scope_id` actif appartient à la catégorie systeme
- Applicatifs parent : actif si `scope_id` actif appartient à la catégorie applicatif
- Sys+App parent : actif si `scope_id` actif appartient à la catégorie systeme_app
- V-Tracker parent : actif si l'un de ses enfants est actif
- Assets : `pathname.startsWith('/assets/')`
- Users : `pathname.startsWith('/users/')`
- Reporting : `pathname.startsWith('/reporting/')`

**Comportement des collapsibles :**
- V-Tracker reste ouvert si on est sur n'importe quelle route `/vtracker/*`
- Systeme/Applicatifs/Sys+App s'ouvrent automatiquement si leur scope actif est sélectionné
- Un seul niveau-2 ouvert à la fois (les deux autres se ferment)

---

### 3. Endpoint API `/api/scopes`

**Fichier :** `app/blueprints/admin/routes.py` (ou `app/blueprints/auth/routes.py`)

**Route :** `GET /api/scopes`
- Protégé par `@jwt_required()`
- Admin uniquement (`@admin_required`)
- Retourne la liste de tous les scopes groupés par catégorie

```python
# Réponse JSON attendue :
{
  "systeme": [
    {"scope_id": 15, "scope_name": "Datacenter Team"},
    {"scope_id": 16, "scope_name": "Linux Team"},
    {"scope_id": 17, "scope_name": "Windows Team"},
    {"scope_id": 18, "scope_name": "Network Team"},
    {"scope_id": 19, "scope_name": "Middleware & Tools"}
  ],
  "applicatif": [
    {"scope_id": 1,  "scope_name": "Digital Workspace"},
    {"scope_id": 2,  "scope_name": "Cyber Security"},
    ...
  ],
  "systeme_app": [
    {"scope_id": 20, "scope_name": "IT Operations & Infrastructures Ops"}
  ]
}
```

**Utilisation dans la sidebar :**
La sidebar JS appelle `vocFetch('/api/scopes')` au chargement pour construire
dynamiquement les sous-menus Systeme / Applicatifs / Sys+App.

---

### 4. Filtre `scope_id` dans V-Tracker

**Fichier :** `app/blueprints/vtracker/routes.py`

**Route concernée :** `GET /vtracker/list`

Ajouter le paramètre `scope_id` (en plus des filtres existants) :

```
scope_id_filter = request.args.get('scope_id', '', type=int)
```

**Logique :**
```
Si is_admin ET scope_id_filter non vide :
    filtrer Asset.scope_id == scope_id_filter
    (remplace le filtre scope habituel)

Si is_admin ET scope_id_filter vide :
    aucun filtre de scope (admin voit tout)

Si not is_admin :
    filtre habituel sur claims['scope_id'] (inchangé, scope_id_filter ignoré)
```

**Titre affiché en haut de la liste :**
```
scope_id_filter vide   → "Vulnérabilités — Tous les scopes"
scope_id_filter renseigné → "Vulnérabilités — <scope_name>"  (requête Scope.query.get(scope_id_filter))
```

**Conserver `scope_id` dans :**
- Les liens de pagination : `?scope_id=...&page=...`
- Le bouton Reset des filtres : `url_for('vtracker.vuln_list', scope_id=scope_id_filter)`

---

### 5. Blueprint Admin — Route Overview

**Fichiers à créer :**
```
app/blueprints/admin/__init__.py
app/blueprints/admin/routes.py
app/templates/admin/overview.html
```

**Route :** `GET /overview/`
- `@jwt_required()`
- `@admin_required`

**Données transmises au template :**

```python
# Jointure : AssetVulnerability → Asset → Scope
# Calculer pour chaque catégorie (applicatif, systeme, systeme_app) :

stats = {
    'applicatif': {
        'total':    int,   # vuln_status != 'Closed'
        'critical': int,   # severity == 'Critical'
        'open':     int,   # vuln_status == 'Open'
        'breached': int,   # SlaTracking.sla_status == 'Breached'
    },
    'systeme':     { ... },
    'systeme_app': { ... },
}

recent_critical = [...]  # 5 dernières vulns Critical, order_by created_at DESC
```

---

### 6. Template Overview (`admin/overview.html`)

**Extends :** `shared/base.html`

**Layout :**

```
┌──────────────────────────────────────────────────────────┐
│  🏠 Overview                                             │
├──────────────────────────────────────────────────────────┤
│  [Applicatifs]       [Systeme]        [Sys+App]          │
│   total     XXX       total  XXX       total  XXX        │
│   critical  XXX       critical XXX     critical XXX      │
│   open      XXX       open    XXX      open    XXX       │
│   breached  XXX       breached XXX     breached XXX      │
│   [→ Voir]            [→ Voir]         [→ Voir]          │
│                                                          │
│  ── Vulnérabilités Critiques Récentes ────────────────── │
│  Asset | IP | Plugin | Scope | Catégorie | Statut | SLA  │
└──────────────────────────────────────────────────────────┘
```

**Cartes KPI :**
- Fond `#161b22`, bordure top colorée :
  - Applicatifs → `#0d6efd` (bleu)
  - Systeme → `#198754` (vert)
  - Sys+App → `#6f42c1` (violet)
- Bouton "→ Voir" renvoie vers `/vtracker/list?scope_cat=<cat>`

---

### 7. Blueprints Assets et Users (stubs indépendants)

**Assets :**
```
app/blueprints/assets/__init__.py
app/blueprints/assets/routes.py   →  GET /assets/   (template stub "Coming soon")
```

**Users :**
```
app/blueprints/users/__init__.py
app/blueprints/users/routes.py    →  GET /users/    (template stub "Coming soon")
```

Enregistrement dans `app/__init__.py` :
```python
try:
    from app.blueprints.assets import assets_bp
    app.register_blueprint(assets_bp, url_prefix='/assets')
except ImportError:
    pass

try:
    from app.blueprints.users import users_bp
    app.register_blueprint(users_bp, url_prefix='/users')
except ImportError:
    pass
```

> La logique métier complète de Assets et Users sera fournie séparément.

---

## Fichiers à créer / modifier — Résumé

| Fichier | Action | Description |
|---|---|---|
| `app/templates/auth/login.html` | Modifier | Redirection post-login selon rôle |
| `app/templates/shared/base.html` | Modifier | Sidebar intelligente avec scopes dynamiques |
| `app/blueprints/admin/__init__.py` | Créer | Blueprint admin |
| `app/blueprints/admin/routes.py` | Créer | `/overview/` + `/api/scopes` |
| `app/templates/admin/overview.html` | Créer | Page overview admin avec KPIs |
| `app/blueprints/assets/__init__.py` | Créer | Blueprint assets (stub) |
| `app/blueprints/assets/routes.py` | Créer | Route `/assets/` stub |
| `app/blueprints/users/__init__.py` | Créer | Blueprint users (stub) |
| `app/blueprints/users/routes.py` | Créer | Route `/users/` stub |
| `app/blueprints/vtracker/routes.py` | Modifier | Ajouter filtre `scope_id` |
| `app/templates/vtracker/list.html` | Modifier | Titre + pagination avec `scope_id` |
| `app/__init__.py` | Modifier | Enregistrer blueprints assets + users |

---

## Contraintes techniques à respecter

- **Dark theme** : variables CSS `--sidebar-bg: #0d1117`, `--sidebar-border: #21262d`
- **Scopes dynamiques** : la sidebar JS charge `/api/scopes` pour construire les sous-menus (pas de hardcode)
- **JWT** : toutes les routes protégées `@jwt_required()` + `vocFetch()` côté JS
- **Isolation scope** : `scope_id` en query param ignoré pour les non-admins (JWT scope prime)
- **Collapsibles Bootstrap** : V-Tracker reste ouvert si pathname commence par `/vtracker/`
- **Assets et Users** : modules totalement séparés de V-Tracker, sections indépendantes dans la sidebar
- **Un scope = une entrée** dans la sidebar, chaque entrée filtre la liste V-Tracker par `scope_id` exact
