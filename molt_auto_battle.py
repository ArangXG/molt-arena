#!/usr/bin/env python3
"""
MoltArena Auto Battle Bot — v5
================================
Auth: Cookie (sb-* dari browser) ATAU API Key (pk_live_...)

CARA DAPAT AUTH:
  Opsi A (API Key - TERMUDAH):
    Buka https://moltarena.crosstoken.io/settings/api → Generate Key
    Isi MOLT_API_KEY=pk_live_... di .env

  Opsi B (Cookie dari browser):
    F12 → Application → Cookies → moltarena.crosstoken.io
    Cari semua cookie sb-* → copy semua → isi MOLT_COOKIE di .env

FLOW VERIFIED (dari HAR):
  Step 1 → POST /api/deploy/battle   {agent1Id, rounds, language, visibility}
  Step 2 → POST /api/battles/{id}/run
  Step 3 → GET  /api/battles/{id}    poll tiap 15 detik
  Delay  → 10 menit → ulangi
"""

import os, sys, time, json, logging, argparse, requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─── Config ───────────────────────────────────────────────────
BASE_URL    = "https://moltarena.crosstoken.io"
API_BASE    = f"{BASE_URL}/api"

AGENT_ID    = os.getenv("MOLT_AGENT_ID",          "")
API_KEY     = os.getenv("MOLT_API_KEY",            "")   # pk_live_...
COOKIE_STR  = os.getenv("MOLT_COOKIE",             "")   # raw cookie string dari browser
DELAY_SEC   = int(os.getenv("MOLT_DELAY_SECONDS",  "600"))
MAX_BATTLES = int(os.getenv("MOLT_MAX_BATTLES",    "0"))
ROUNDS      = int(os.getenv("MOLT_ROUNDS",         "5"))

# ─── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("molt_battle.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("MoltBot")


# ─── Build headers dengan auth ────────────────────────────────
def _headers(with_body: bool = False) -> dict:
    h = {
        "accept":          "*/*",
        "accept-language": "en-US,en;q=0.9",
        "origin":          BASE_URL,
        "referer":         f"{BASE_URL}/battles/new",
        "user-agent":      (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36"
        ),
    }
    if with_body:
        h["content-type"] = "application/json"

    # Auth — API Key lebih prioritas
    if API_KEY:
        h["authorization"] = f"Bearer {API_KEY}"
    elif COOKIE_STR:
        h["cookie"] = COOKIE_STR

    return h


# ─── HTTP ─────────────────────────────────────────────────────
def api_get(path: str) -> dict | None:
    try:
        r = requests.get(f"{API_BASE}{path}", headers=_headers(), timeout=30)
        log.debug(f"GET {path} → {r.status_code}")
        if r.status_code == 200:
            return r.json()
        log.error(f"GET {path} → {r.status_code}: {r.text[:150]}")
        return None
    except Exception as e:
        log.error(f"GET {path} → {e}")
        return None

def api_post(path: str, payload: dict | None = None) -> dict | None:
    try:
        if payload is not None:
            r = requests.post(f"{API_BASE}{path}", headers=_headers(True), json=payload, timeout=30)
        else:
            r = requests.post(f"{API_BASE}{path}", headers=_headers(), timeout=30)
        log.debug(f"POST {path} → {r.status_code}: {r.text[:200]}")
        if r.status_code in (200, 201):
            return r.json()
        return {"_error": True, "_status": r.status_code, "_body": r.text[:300]}
    except Exception as e:
        log.error(f"POST {path} → {e}")
        return None


# ─── Battle Steps ─────────────────────────────────────────────
def create_battle() -> dict | None:
    log.info("  📤 Step 1: POST /api/deploy/battle")
    return api_post("/deploy/battle", {
        "agent1Id":   AGENT_ID,
        "rounds":     ROUNDS,
        "language":   "en",
        "visibility": "public",
    })

def run_battle(battle_id: str) -> dict | None:
    log.info(f"  ▶️  Step 2: POST /api/battles/{battle_id}/run")
    return api_post(f"/battles/{battle_id}/run")

def poll_battle(battle_id: str, max_wait: int = 300) -> dict | None:
    log.info("  🔄 Step 3: Polling hasil...")
    done = {"completed", "finished", "done", "ended", "voting"}
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(15)
        elapsed += 15
        data = api_get(f"/battles/{battle_id}")
        if not data:
            continue
        battle = data.get("battle", data)
        status = str(battle.get("status", "")).lower()
        cur_r  = battle.get("currentRound", "?")
        log.info(f"  ⌛ [{status.upper()}] Round {cur_r}/{ROUNDS} | {elapsed}s")
        if status in done:
            return battle
    log.warning("  ⚠️  Timeout polling, lanjut cooldown...")
    return None

def print_result(battle: dict):
    if not battle: return
    agent_a   = battle.get("agentA") or {}
    agent_b   = battle.get("agentB") or {}
    name_a    = agent_a.get("name", "Agent A")
    name_b    = agent_b.get("name", "Agent B")
    winner_id = battle.get("winnerId")
    log.info("  " + "─"*52)
    log.info(f"  🔥 Battle #{battle.get('battleNumber','?')} — {battle.get('topic','?')}")
    log.info(f"  ⚔️  {name_a}  vs  {name_b}")
    if winner_id:
        winner = name_a if winner_id == agent_a.get("id") else name_b
        log.info(f"  🏆 Winner : {winner}")
    log.info(f"  🗳️  Votes  : {name_a}={battle.get('voteCountA',0)} | {name_b}={battle.get('voteCountB',0)}")
    log.info(f"  🔗 {BASE_URL}/battle/{battle.get('id','?')}")
    log.info("  " + "─"*52)

def countdown(seconds: int):
    log.info(f"\n  ⏳ Cooldown {seconds//60}m {seconds%60}s...\n")
    end = time.time() + seconds
    next_log = time.time() + 60
    while time.time() < end:
        time.sleep(1)
        if time.time() >= next_log:
            rem = int(end - time.time())
            log.info(f"  ⌛ Sisa: {rem//60}m {rem%60}s")
            next_log = time.time() + 60
    log.info("  ✅ Cooldown selesai!\n")


# ─── Validasi ─────────────────────────────────────────────────
def validate():
    errs = []
    if not AGENT_ID:
        errs.append("MOLT_AGENT_ID belum diset")
    if not API_KEY and not COOKIE_STR:
        errs.append(
            "Auth belum diset! Isi salah satu:\n"
            "    MOLT_API_KEY=pk_live_...   (dari settings/api)\n"
            "    MOLT_COOKIE=sb-...         (dari browser Application tab)"
        )
    if errs:
        for e in errs: log.error(f"❌ {e}")
        sys.exit(1)

    auth_type = "API Key" if API_KEY else "Cookie"
    log.info(f"  🔑 Auth   : {auth_type}")
    log.info(f"  🤖 Agent  : {AGENT_ID}")
    log.info(f"  🎯 Rounds : {ROUNDS}")
    log.info(f"  ⏱  Delay  : {DELAY_SEC}s ({DELAY_SEC//60} menit)")
    log.info(f"  🔄 Max    : {'∞ infinite' if MAX_BATTLES==0 else f'{MAX_BATTLES} battles'}")


# ─── Main Loop ────────────────────────────────────────────────
def main(max_override: int = None):
    max_b = max_override if max_override is not None else MAX_BATTLES

    log.info("=" * 58)
    log.info("  🥊 MoltArena Auto Battle Bot v5")
    log.info("  Mode: 1v1 Roast | Random Match | English")
    log.info("=" * 58 + "\n")

    validate()

    count = 0
    log.info("🚀 Loop battle dimulai!\n")

    while True:
        count += 1
        log.info(f"{'='*58}")
        log.info(f"  ⚔️  Battle ke-{count}  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log.info(f"{'='*58}")

        r1 = create_battle()

        if r1 is None:
            log.warning("  ⚠️  Tidak bisa connect server")
        elif r1.get("_error"):
            s = r1["_status"]
            b = r1.get("_body","")
            if s in (401, 403):
                log.error("  ❌ AUTH GAGAL!")
                if not API_KEY and not COOKIE_STR:
                    log.error("  → Isi MOLT_API_KEY atau MOLT_COOKIE di .env")
                elif API_KEY:
                    log.error("  → API Key mungkin expired/salah. Cek settings/api")
                else:
                    log.error("  → Cookie mungkin expired. Ambil cookie baru dari browser")
                sys.exit(1)
            elif s == 429:
                log.warning("  🚦 Rate limit — tunggu 2 menit extra...")
                time.sleep(120)
            else:
                log.warning(f"  ⚠️  HTTP {s}: {b[:150]}")
        else:
            battle_raw = r1.get("battle", r1)
            battle_id  = battle_raw.get("id") or r1.get("battleId")
            log.info(f"  ✅ Battle #{battle_raw.get('battleNumber','?')} dibuat!")
            log.info(f"  📌 Topic: {battle_raw.get('topic','?')}")

            if battle_id:
                time.sleep(2)
                r2 = run_battle(battle_id)
                if r2 and not r2.get("_error"):
                    log.info(f"  ✅ {r2.get('message','Battle berjalan!')}")
                else:
                    log.warning("  ⚠️  /run gagal, tetap polling...")

                time.sleep(5)
                result = poll_battle(battle_id, max_wait=300)
                print_result(result or battle_raw)

        if max_b > 0 and count >= max_b:
            log.info(f"\n✅ Selesai! {max_b} battles tercapai.")
            break

        countdown(DELAY_SEC)

    log.info(f"\n🏁 Bot selesai. Total: {count} battles")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--once",  action="store_true")
    p.add_argument("--debug", action="store_true")
    args = p.parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    try:
        main(max_override=1 if args.once else None)
    except KeyboardInterrupt:
        log.info("\n⛔ Dihentikan. Bye!")
        sys.exit(0)
