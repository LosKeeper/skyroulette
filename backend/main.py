# backend/main.py
import discord
import random
import os
import threading
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends, Request, HTTPException
from dotenv import load_dotenv
import state
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import asyncio

load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.presences = True

bot = discord.Client(intents=intents)
app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


GUILD_ID = int(os.getenv("GUILD_ID"))


async def timeout_random():
    guild = bot.get_guild(GUILD_ID)

    # On recalcule la liste au moment du spin
    candidates = [
        m for m in guild.members
        if (
            not m.bot
            and m.status != discord.Status.offline
            and m != guild.owner
            and not m.guild_permissions.administrator
        )
    ]

    if not candidates:
        return None

    victim = random.choice(candidates)
    bot.loop.create_task(
        victim.timeout(timedelta(minutes=2), reason="🎰 Skyroulette Discord")
    )
    # enregistrer avec durée (2 minutes)
    state.register_spin(victim.display_name, minutes=2)
    return victim.display_name


@app.get("/config")
async def config(request: Request):
    # Ne pas exposer de clé API publique par défaut.
    return {}


@app.post("/spin")
async def spin(request: Request):
    # Vérification d'origine minimale : autoriser uniquement les requêtes
    # provenant de l'origine configurée via `ALLOWED_ORIGIN` (optionnel).
    origin = request.headers.get("origin") or request.headers.get("referer")
    allowed = os.getenv("ALLOWED_ORIGIN", "")
    if allowed:
        if not origin or (not origin.startswith(allowed)):
            raise HTTPException(status_code=403, detail="Forbidden")

    if not state.can_spin():
        return {"status": "cooldown"}

    name = await timeout_random()
    if not name:
        return {"status": "empty"}

    return {"status": "ok", "member": name}


@app.get("/status")
async def status():
    return {
        "online": len(state.online_members),
        "can_spin": state.can_spin(),
        "history": state.history[-5:]
    }


@app.get("/history")
async def get_history():
    now = datetime.now(timezone.utc)
    enriched = []

    for entry in state.history:
        ends_at_iso = entry.get("ends_at")
        active = False

        try:
            if ends_at_iso:
                ends = datetime.fromisoformat(ends_at_iso)
                if ends.tzinfo is None:
                    ends = ends.replace(tzinfo=timezone.utc)
                active = now < ends
        except Exception:
            active = False

        enriched.append({
            "member": entry.get("member"),
            "time": (
                datetime.fromisoformat(entry["time"])
                .replace(tzinfo=timezone.utc)
                .isoformat()
            ),
            "ends_at": (
                datetime.fromisoformat(entry["ends_at"])
                .replace(tzinfo=timezone.utc)
                .isoformat()
                if entry.get("ends_at") else None
            ),
            "active": active
        })

    return {"history": enriched}


def run_bot():
    bot.run(os.getenv("DISCORD_TOKEN"))


threading.Thread(target=run_bot, daemon=True).start()
