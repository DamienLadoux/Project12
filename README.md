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

Installer les dépendances :

```powershell
python -m pip install -r requirements.txt
```

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

```powershell
python -m pytest -q
```
