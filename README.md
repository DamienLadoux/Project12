# Epic Events CRM

Application CRM en ligne de commande utilisant PostgreSQL et SQLAlchemy.

## Configuration

Créer un fichier `.env` à partir de `.env.example`, puis renseigner les
paramètres PostgreSQL. Le fichier `.env` est ignoré par Git.

Générer un secret JWT aléatoire :

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copier le résultat dans `JWT_SECRET`. Le secret doit contenir au moins 32
octets et ne doit jamais être enregistré dans Git.

La supervision Sentry est facultative en développement. Pour l'activer,
renseigner `SENTRY_DSN` et, si nécessaire, `SENTRY_ENVIRONMENT` dans `.env`.
L'application envoie les erreurs techniques non gérées ainsi que les
événements d'audit suivants : connexions réussies, créations ou modifications
de collaborateurs et signatures de contrat.
Seuls les identifiants techniques et le rôle du collaborateur sont associés
à ces événements ; les mots de passe et données personnelles sont exclus.

Installer les dépendances :

```powershell
python -m pip install -r requirements.txt
```

## Initialisation de PostgreSQL

Créer d'abord un compte PostgreSQL non privilégié réservé à l'application,
par exemple avec pgAdmin ou la commande SQL suivante exécutée par un
administrateur :

```sql
CREATE ROLE epic_events_user LOGIN PASSWORD 'mot_de_passe_a_remplacer';
```

Renseigner dans `.env` les variables `ADMIN_DB_*` du compte autorisé à créer
une base, puis les variables `DB_*` du compte applicatif. Créer ensuite la
base, son schéma et le premier compte du département gestion :

```powershell
python init_database.py
python create_schema.py
python bootstrap.py
```

`init_database.py` crée la base avec `DB_USER` comme propriétaire. Si la base
existe déjà, il faut vérifier manuellement que ce compte dispose des droits
sur la base et le schéma `public`. `bootstrap.py` crée les rôles `GESTION`,
`COMMERCIAL` et `SUPPORT`, puis demande interactivement les informations du
premier gestionnaire. Par sécurité, ce script refuse de créer un compte dès
qu'un collaborateur existe déjà.

## Interface en ligne de commande

`argparse` analyse les commandes et valide leur structure. Rich présente les
listes sous forme de tableaux et distingue visuellement les confirmations,
les informations et les erreurs. La logique métier reste dans `services/` :
l'interface se limite à valider la saisie, appeler un service et afficher son
résultat.

Afficher l'aide générale ou celle d'une commande :

```powershell
python epicevents.py --help
python epicevents.py events --help
python epicevents.py events update --help
```

Les identifiants doivent être strictement positifs. Le nombre de participants
doit être positif ou nul. Les dates, e-mails, montants et autres règles métier
sont également validés par les services avant toute écriture.

## Authentification persistante

Ouvrir une session pour huit heures :

```powershell
python epicevents.py login
```

Vérifier le compte connecté :

```powershell
python epicevents.py whoami
```

Fermer la session :

```powershell
python epicevents.py logout
```

Le JWT local ne contient que l'identifiant du collaborateur. À chaque
commande, l'application valide sa signature et son expiration, puis recharge
le compte et son rôle depuis PostgreSQL. Une modification ou suppression du
compte prend donc effet sans attendre l'expiration du jeton.

Le jeton est stocké dans le répertoire applicatif de l'utilisateur :

- `%LOCALAPPDATA%\EpicEvents\access_token` sous Windows ;
- `$XDG_STATE_HOME/epic-events/access_token` sous Unix, ou
  `~/.local/state/epic-events/access_token` en l'absence de cette variable.

## Tests

Tests unitaires rapides, sans PostgreSQL ni stockage persistant :

```powershell
python -m pytest tests/unit -q
```

Mesurer la couverture des tests :

```powershell
python -m pytest --cov=. --cov-report=term-missing -q
```

Contrôler la qualité et le style Python :

```powershell
python -m ruff check .
```

Tests d'intégration avec PostgreSQL ou le système de fichiers :

```powershell
python -m pytest tests/integration -q
```

Suite complète :

```powershell
python -m pytest -q
```

## Commandes métier

Toutes les commandes métier exigent une session ouverte avec `login`.
L'aide complète d'une commande reste disponible avec `--help`.

### Collaborateurs — département gestion

```powershell
python epicevents.py employees list
python epicevents.py employees create --number EMP-004 --name "Alice Martin" --email alice@example.com --role SUPPORT
python epicevents.py employees update 4 --number EMP-014 --role COMMERCIAL
python epicevents.py employees update 4 --change-password
python epicevents.py employees delete 4
```

Le mot de passe initial ou modifié est demandé interactivement afin qu'il
n'apparaisse pas dans l'historique du terminal.

### Clients

```powershell
python epicevents.py clients list
python epicevents.py clients list --mine
python epicevents.py clients create --name "Client test" --email client@example.com --company "Entreprise test"
python epicevents.py clients update 1 --phone "01 02 03 04 05" --last-contact 2026-10-21
python epicevents.py clients update 1 --clear-phone
```

La création est réservée aux commerciaux. Un commercial ne peut modifier
que les clients dont il est responsable.

### Contrats

```powershell
python epicevents.py contracts list
python epicevents.py contracts list --unsigned --unpaid
python epicevents.py contracts list --mine
python epicevents.py contracts create 1 --total 5000.00 --remaining 5000.00
python epicevents.py contracts update 1 --client-id 2 --remaining 2500.00 --signed
```

Seul le département gestion peut créer ou modifier un contrat.

### Événements

Les dates utilisent le format ISO 8601 et doivent contenir un fuseau horaire.

```powershell
python epicevents.py events list
python epicevents.py events list --mine
python epicevents.py events list --without-support
python epicevents.py events create 1 --name "Gala" --start "2026-11-01T09:00:00+01:00" --end "2026-11-01T18:00:00+01:00" --location "Paris" --attendees 150
python epicevents.py events update 1 --contract-id 2 --attendees 175 --notes "Accueil à 8 h 30"
python epicevents.py events assign-support 1 --support-id 4
python epicevents.py events assign-support 1 --clear
```

Le commercial responsable crée l'événement lorsque le contrat est signé.
La gestion affecte le support, puis seul le support affecté peut modifier
l'événement.

Chaque commande métier s'exécute dans une transaction SQLAlchemy. En cas de
succès, la transaction est validée ; en cas d'erreur, elle est annulée dans
son ensemble.
