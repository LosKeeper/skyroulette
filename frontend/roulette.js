// frontend/roulette.js
// Pas de clé exposée côté client

const wheel = document.getElementById("wheel");
const btn = document.getElementById("spin-btn");
const resultEl = document.getElementById("result");
const historyList = document.getElementById("history");
const clearBtn = document.getElementById("clear-history");
const leaderboardEl = document.getElementById("leaderboard");

const SPIN_DURATION_MS = 5000;
const HISTORY_KEY = "skyroulette_history_v1";
const MAX_DISPLAY = 5;

let history = [];

// bouton activé par défaut

// util: format date FR
function formatDate(ts) {
    const d = typeof ts === "number"
        ? new Date(ts * 1000) // timestamp UNIX
        : new Date(ts);

    return new Intl.DateTimeFormat("fr-FR", {
        timeZone: "Europe/Paris",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    }).format(d);
}


function initialsFromName(name) {
    if (!name) return "??";
    const parts = name.trim().split(/\s+/);
    return (parts[0][0] || "").toUpperCase() + (parts[1] ? (parts[1][0] || "").toUpperCase() : "");
}

function saveLocalHistory() {
    try {
        localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    } catch (e) { }
}

function loadLocalHistory() {
    try {
        const raw = localStorage.getItem(HISTORY_KEY);
        history = raw ? JSON.parse(raw) : [];
    } catch (e) {
        history = [];
    }
}

function getLastEntries(arr, n) {
    if (!Array.isArray(arr)) return [];
    return arr.slice(Math.max(0, arr.length - n));
}

function renderHistory() {
    historyList.innerHTML = "";
    const toDisplay = getLastEntries(history, MAX_DISPLAY);
    if (!toDisplay || toDisplay.length === 0) {
        historyList.innerHTML = '<li class="history-empty">Aucun timeout enregistré.</li>';
        return;
    }
    // afficher du plus récent au plus ancien
    for (const item of toDisplay.slice().reverse()) {
        const li = document.createElement("li");
        li.className = "history-item";

        const endsAt = item.ends_at ? new Date(item.ends_at) : null;
        const active = (typeof item.active !== "undefined") ? item.active : (endsAt ? (Date.now() < endsAt.getTime()) : false);

        const endsText = endsAt ? ` -> ${formatDate(item.ends_at)}` : "";

        li.innerHTML = `
            <div class="avatar">${initialsFromName(item.member)}</div>
            <div class="meta">
                <div class="member">${item.member}</div>
                <div class="time">${formatDate(item.time)}${endsText}</div>
            </div>
            <div class="badge">${active ? 'En cours' : 'Terminé'}</div>
        `;
        historyList.appendChild(li);
    }
}

// Essaie de charger l'historique depuis le serveur, fallback sur local
async function loadHistory() {
    try {
        const res = await fetch("/history");
        if (res.ok) {
            const data = await res.json();
            // garder seulement les derniers MAX_DISPLAY éléments côté client
            history = data.history || [];
            history = getLastEntries(history, MAX_DISPLAY);
            saveLocalHistory(); // mise en cache locale si besoin
            renderHistory();
            return;
        }
    } catch (e) {
        // ignore, on utilisera le local
    }
    loadLocalHistory();
    history = getLastEntries(history, MAX_DISPLAY);
    renderHistory();
}


async function loadTopBanned() {
    if (!leaderboardEl) return;
    try {
        const res = await fetch('/top-banned?limit=5');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();

        if (!Array.isArray(data) || data.length === 0) {
            leaderboardEl.innerHTML = '<div class="leaderboard-empty">Aucune donnée</div>';
            return;
        }

        // On génère le HTML pour chaque entrée du top 5
        // On ajoute un petit margin-bottom inline pour l'espacement car le conteneur n'a pas de gap défini
        const html = data.map(item => `
            <div class="leaderboard-entry" style="margin-bottom: 8px;">
                <div class="avatar-lg">${initialsFromName(item.member)}</div>
                <div class="meta-lg">
                    <div class="member-lg">${item.member}</div>
                    <div class="time-lg">${item.total_minutes} minutes cumulées</div>
                </div>
            </div>
        `).join('');

        leaderboardEl.innerHTML = html;
    } catch (e) {
        leaderboardEl.innerHTML = '<div class="leaderboard-empty">Erreur de chargement</div>';
    }
}

clearBtn.addEventListener("click", () => {
    if (!confirm("Effacer l'historique local ? (l'historique serveur reste inchangé)")) return;
    history = [];
    saveLocalHistory();
    renderHistory();
});

// initial load
loadHistory();
loadTopBanned();

btn.addEventListener("click", async () => {
    btn.disabled = true;
    resultEl.className = "result"; // reset classes
    resultEl.textContent = "";

    // Rotation aléatoire
    const segments = 6;
    const randomIndex = Math.floor(Math.random() * segments);
    const extraRounds = 5 + Math.floor(Math.random() * 5); // 5-9 tours
    const degrees = 360 * extraRounds + (randomIndex * (360 / segments)) + (Math.random() * (360 / segments));

    // lancer animation
    wheel.style.transition = `transform ${SPIN_DURATION_MS}ms cubic-bezier(0.33, 1, 0.68, 1)`;
    wheel.style.transform = `rotate(${degrees}deg)`;

    // animation de pointer (petit rebond)
    wheel.classList.add("spinning");

    // Appel backend après l'animation
    setTimeout(async () => {
        try {
            const res = await fetch("/spin", { method: "POST" });
            if (!res.ok) throw new Error("HTTP " + res.status);
            const data = await res.json();

            if (data.status === "ok") {
                const member = data.member || "Inconnu";
                resultEl.innerText = `💀 ${member} a été timeout`;
                resultEl.classList.add("success");

                // Rafraîchir depuis le serveur pour récupérer l'historique partagé (et n'afficher que les 5 derniers)
                setTimeout(() => { loadHistory(); loadTopBanned(); }, 400);
            } else if (data.status === "cooldown") {
                resultEl.innerText = "⏳ Roulette en cooldown, réessayez plus tard";
                resultEl.classList.add("note");
            } else {
                resultEl.innerText = "❌ Aucun membre éligible";
                resultEl.classList.add("error");
            }
        } catch (err) {
            resultEl.innerText = "⚠️ Erreur serveur";
            resultEl.classList.add("error");
        } finally {
            // reset rotation pour éviter overflow des transforms (conserver angle final visuel)
            setTimeout(() => {
                const computed = window.getComputedStyle(wheel).transform;
                wheel.style.transition = "none";
                wheel.style.transform = computed;
                setTimeout(() => {
                    wheel.style.transition = '';
                    wheel.classList.remove("spinning");
                    btn.disabled = false;
                }, 50);
            }, 100);
        }
    }, SPIN_DURATION_MS);
});

async function checkStatus() {
    try {
        const res = await fetch("/status");
        if (res.ok) {
            const data = await res.json();
            const banner = document.getElementById("happy-hour-banner");
            if (banner) {
                if (data.happy_hour) {
                    banner.classList.remove("hidden");
                    // mettre à jour les heures affichées si fournies par le backend
                    try {
                        const hoursEl = banner.querySelector('.happy-hour-hours');
                        if (hoursEl && typeof data.happy_hour_start !== 'undefined' && typeof data.happy_hour_end !== 'undefined') {
                            const pad = (n) => String(n).padStart(2, '0');
                            hoursEl.textContent = `de ${pad(data.happy_hour_start)}h à ${pad(data.happy_hour_end)}h`;
                        }
                    } catch (e) {
                        // ignore
                    }
                } else {
                    banner.classList.add("hidden");
                }
            }
        }
    } catch (e) {
        console.error("Failed to check status", e);
    }
}

checkStatus();
setInterval(checkStatus, 60000);
