# backend/main.py
import time
import discord
import random
import os
import threading
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends, Request, HTTPException
from dotenv import load_dotenv
import state
import timeouts_store
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import asyncio

load_dotenv()

# Use SystemRandom for stronger, OS-backed randomness (thread-safe source)
sysrand = random.SystemRandom()
# Lock to protect selection & state updates when called concurrently
selection_lock = threading.Lock()

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

    # protect selection + registration to avoid races when /spin is called
    # concurrently from multiple threads/workers
    with selection_lock:
        victim = sysrand.choice(candidates)
        # schedule timeout (non-blocking)
        bot.loop.create_task(
            victim.timeout(timedelta(minutes=2),
                           reason="🎰 Skyroulette Discord")
        )
        # enregistrer avec durée (2 minutes)
        state.register_spin(victim.display_name, minutes=2)
    # Annoncer le spin et le membre banni dans le channel configuré
    announce_channel = os.getenv("ANNOUNCE_CHANNEL_ID")
    if announce_channel:
        try:
            channel = bot.get_channel(int(announce_channel))
            if channel:
                templates = [
                    "🎡 La roue tourne... *tic tac* 🎶 {mention} a atterri sur la case PERDU · banni·e {minutes} minutes ! ⏳💥",
                    "🛑 BOOM ! {mention} a été choisi·e par la destinée — {minutes} minutes de timeout. 🎲",
                    "🥀 Oh non, {mention}... la roue t'a décidé pour toi. Pause de {minutes} minutes, reviens-nous en un morceau. 😅",
                    "🏴‍☠️ Par les sabres ! {mention} est envoyé·e au coffre pendant {minutes} minutes. Arrr!",
                    "✨ Destin accompli : {mention} prend un petit break de {minutes} minutes. Profites-en pour boire un café ☕",
                    "🎯 Coup de théâtre : {mention} ciblé·e — {minutes} minutes pour méditer ses choix. 🧘",
                    "🔥 Quelle chaleur ! {mention} se retrouve en cooldown pendant {minutes} minutes. Rafraîchis-toi. ❄️",
                    "🤖 Système: Randomizer a sélectionné {mention}. Maintenance programmée: {minutes} minutes."
                ]
                chosen = sysrand.choice(templates)
                message = chosen.format(
                    name=victim.display_name, mention=victim.mention, minutes=2)
                # Envoyer via la boucle du bot pour éviter "Timeout context manager"
                try:
                    bot.loop.create_task(channel.send(message))
                except Exception:
                    # Fallback: tenter d'appeler thread-safe
                    try:
                        bot.loop.call_soon_threadsafe(
                            asyncio.create_task, channel.send(message))
                    except Exception:
                        pass
        except Exception:
            pass
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
    guild = bot.get_guild(GUILD_ID)

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

        # resolve latest display name if we have a member_id and the guild
        display = entry.get("member")
        member_id = entry.get("member_id")
        if member_id and guild:
            try:
                member_obj = guild.get_member(int(member_id))
                if member_obj:
                    display = member_obj.display_name
            except Exception:
                pass

        enriched.append({
            "member": display,
            "member_id": member_id,
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


@app.get("/top-banned")
async def top_banned(limit: int = 1):
    """Retourne la liste des personnes ayant cumulé le plus de temps de timeout.

    Args:
        limit (int): Nombre maximum de membres à retourner (défaut: 1).
    """
    totals = {}
    guild = bot.get_guild(GUILD_ID)
    for entry in state.history:
        # prefer aggregating by member_id when available
        member_key = entry.get("member_id") or entry.get("member")
        starts_iso = entry.get("time")
        ends_iso = entry.get("ends_at")
        if not member_key or not starts_iso or not ends_iso:
            continue
        try:
            starts = datetime.fromisoformat(starts_iso)
            ends = datetime.fromisoformat(ends_iso)
            if starts.tzinfo is None:
                starts = starts.replace(tzinfo=timezone.utc)
            if ends.tzinfo is None:
                ends = ends.replace(tzinfo=timezone.utc)
            duration = (ends - starts).total_seconds()
            if duration > 0:
                totals[member_key] = totals.get(member_key, 0) + duration
        except Exception:
            continue

    if not totals:
        return []

    # Tri par durée décroissante
    sorted_totals = sorted(
        totals.items(), key=lambda item: item[1], reverse=True)

    # Récupération des N premiers
    top_n = sorted_totals[:limit]

    results = []
    for member_key, total_sec in top_n:
        secs = int(total_sec)
        minutes = secs // 60
        display = member_key
        # try to resolve member_id -> display name
        if guild and str(member_key).isdigit():
            try:
                mem = guild.get_member(int(member_key))
                if mem:
                    display = mem.display_name
            except Exception:
                pass
        results.append({
            "member": display,
            "member_key": member_key,
            "total_seconds": secs,
            "total_minutes": minutes
        })

    return results


def run_bot():
    bot.run(os.getenv("DISCORD_TOKEN"))


threading.Thread(target=run_bot, daemon=True).start()


# Migration: update existing history entries with `member_id` when possible
@bot.event
async def on_ready():
    try:
        guild = bot.get_guild(GUILD_ID)
    except Exception:
        guild = None

    if not guild:
        return

    updated = False
    for entry in state.history:
        if entry.get("member_id"):
            continue
        name = entry.get("member")
        if not name:
            continue
        # best-effort: try to match display_name or username
        for m in guild.members:
            try:
                if m.display_name == name or m.name == name:
                    entry["member_id"] = str(m.id)
                    updated = True
                    break
            except Exception:
                continue

    if updated:
        try:
            timeouts_store.save_history(state.history)
            print("[migration] updated timeouts.json with member_id for some entries")
        except Exception:
            print("[migration] failed to save migrated timeouts.json")
