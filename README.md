# Skyroulette

Petit service FastAPI + bot Discord qui propose un "spin" pour ban temporairement un membre.

Installation
- Installer les dépendances :

```bash
pip install -r backend/requirements.txt
```

Configuration
- Créer un fichier `.env` dans `backend/` contenant au minimum :

- `DISCORD_TOKEN` : token du bot Discord
- `GUILD_ID` : identifiant du serveur (entier)
- `ALLOWED_ORIGIN` (optionnel) : origine autorisée pour les requêtes depuis le frontend, par ex. `http://localhost:8000`. Si défini, le serveur refusera les POST vers `/spin` provenant d'une autre origine.

Exécution
- Depuis la racine du projet :

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Le serveur FastAPI sert le frontend (route `/` et `/static`) et démarre le bot Discord en arrière-plan.

Endpoints principaux
- `POST /spin` : lance un spin si possible. Le serveur applique une vérification d'origine si `ALLOWED_ORIGIN` est configuré.
- `GET /status` : informations rapides (online, candidates, can_spin, history).
- `GET /history` : historique enrichi des spins.

Persistance et endpoints connexes
- Le backend persiste l'historique des spins dans `backend/timeouts.json` via le module `backend/timeouts_store.py`. Le fichier est créé automatiquement et écrit de façon sûre.
- Un nouvel endpoint `GET /top-banned` renvoie les N personnes ayant cumulé le plus de temps de timeout (format curseur sur : `{"member": <nom>, "total_seconds": <int>, "duration_str": <format H-M-S>}`).

Frontend
- La page front affiche désormais un "Leaderboard" reprenant le résultat de `/top-banned`. Le client (`frontend/roulette.js`) récupère ce résultat au chargement et l'actualise après chaque spin.

Notes
- Le frontend est dans le dossier `frontend/` et est monté sur `/static`.
- Pour pinner des versions exactes, exécuter `pip freeze > backend/requirements.txt` dans un environnement contrôlé.
