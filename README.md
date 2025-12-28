# Skyroulette

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/github/license/LosKeeper/skyroulette)](https://github.com/LosKeeper/skyroulette/blob/main/LICENSE)
[![Stars](https://img.shields.io/github/stars/LosKeeper/skyroulette?style=social)](https://github.com/LosKeeper/skyroulette/stargazers)
[![GitHub profile](https://img.shields.io/badge/GitHub-LosKeeper-181717?logo=github&logoColor=white)](https://github.com/LosKeeper)
[![GitHub profile](https://img.shields.io/badge/GitHub-ThomasByr-181717?logo=github&logoColor=red)](https://github.com/ThomasByr)

A small web service combining a FastAPI backend and a Discord bot: the application offers a random "spin" which applies a temporary timeout (short ban) to an eligible member of a Discord guild.

**Quick facts**
- Language: Python 3.8+
- Backend: FastAPI (REST API) + Discord bot (discord.py)
- Frontend: static page (HTML/CSS/JS) served by the backend
- Deployment: example systemd unit in `deploy/`

**Features**
- Trigger a random spin via `POST /spin` to select an eligible member.
- Persisted timeout history in `backend/timeouts.json`.
- `GET /top-banned` endpoint: leaderboard of members with the most accumulated timeout time.
- Configurable "Happy Hour": reduced timeout durations and shorter cooldowns.

**Repository layout (high level)**
- `backend/`: server and bot code (`main.py`, `state.py`, `timeouts_store.py`, `data.py`, `run.sh`, `requirements.txt`).
- `frontend/`: static assets served at `/` (`index.html`, `roulette.js`, `style.css`).
- `deploy/`: `skyroulette.service` example for systemd deployment.

**Configuration (.env)**
Create a `.env` file in `backend/` containing at least:

- `DISCORD_TOKEN`: Discord bot token
- `GUILD_ID`: target guild ID (integer)
- `ANNOUNCE_CHANNEL_ID`: channel ID for spin announcements (optional)
- `ALLOWED_ORIGIN`: allowed origin for requests from the frontend (optional)
- `START_HOUR_HAPPY_HOUR`, `END_HOUR_HAPPY_HOUR`: daily happy hour start/end (24h, optional)

Note: `backend/run.sh` reads `.env` and activates a local `venv` if present.

**Quick start (development)**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# copy and adapt .env
./run.sh
```

`run.sh` launches `uvicorn` on `0.0.0.0:8000` and runs the Discord bot alongside the API.

**Important endpoints**
- `GET /`: serves the frontend (`frontend/index.html`).
- `POST /spin`: triggers a spin (origin check if `ALLOWED_ORIGIN` is set).
- `GET /status`: quick status (online, candidates, can_spin, happy_hour, cooldown_seconds, history).
- `GET /history`: enriched history of recent spins.
- `GET /top-banned?limit=N`: top N members by total timeout seconds.

**Systemd deployment**
An example systemd unit is available at `deploy/skyroulette.service`. Adapt paths and user before enabling. Minimal example:
```bash
sudo cp deploy/skyroulette.service /etc/systemd/system/skyroulette.service
sudo systemctl daemon-reload
sudo systemctl enable --now skyroulette.service
```

**Security & best practices**
- Never commit your `DISCORD_TOKEN` or `.env` to a public repository.
- Restrict `ALLOWED_ORIGIN` if serving a public frontend.
- Pin dependency versions in `requirements.txt` for production deployments.

**Development notes**
- The Discord bot is started in a background thread from `backend/main.py`; API routes interact with the bot via the `bot` object.
- Application state (cooldown, history) is handled by `backend/state.py` and persisted through `backend/timeouts_store.py`.

**Contributing**
- Please open an issue or a pull request on the repository explaining your change.

**Acknowledgements / Contributors**
Thank you to the contributors — add names below:
- [Thomas Byr](https://github.com/ThomasByr) — fix and improvements to frontend and backend.

**References**
- Code: [backend/main.py](backend/main.py#L1)
- Frontend: [frontend/index.html](frontend/index.html#L1)
- Systemd unit: [deploy/skyroulette.service](deploy/skyroulette.service#L1)

