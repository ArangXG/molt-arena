#!/usr/bin/env python3
"""
MoltArena Auto Battle Bot — v4 (FINAL)
========================================
Verified dari HAR real browser:
  ✅ TIDAK butuh Authorization header
  ✅ TIDAK butuh Cookie
  ✅ Hanya butuh agent1Id di payload

FLOW TERVERIFIKASI:
  Step 1 → POST /api/deploy/battle        payload: {agent1Id, rounds, language, visibility}
  Step 2 → POST /api/battles/{id}/run     (jalankan battle, no body)
  Step 3 → GET  /api/battles/{id}         (poll tiap 15 detik)
  Delay  → tunggu 10 menit
  Loop   → ulangi dari Step 1
"""

import os, sys, time, json, logging, argparse
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────
BASE_URL    = "https://moltarena.crosstoken.io"
API_BASE    = f"{BASE_URL}/api"

AGENT_ID    = os.getenv("MOLT_AGENT_ID",          "")
DELAY_SEC   = int(os.getenv("MOLT_DELAY_SECONDS", "600"))   # 10 menit default
MAX_BATTLES = int(os.getenv("MOLT_MAX_BATTLES",   "0"))     # 0 = infinite
ROUNDS      = int(os.getenv("MOLT_ROUNDS",        "5"))

# ─── Logging ──────────────────────────────────────────────────────────────────
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


# ─── Headers (persis seperti di browser / HAR) ────────────────────────────────
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
    return h


# ─── HTTP Helper ──────────────────────────────────────────────────────────────
def api_get(path: str) -> dict | None:
    url = f"{API_BASE}{path}"
    try:
        r = requests.get(url, headers=_headers(), timeout=30)
        log.debug(f"GET {path} → {r.status_code}")
        if r.status_code == 200:
            return r.json()
        log.error(f"GET {path} → {r.status_code}: {r.text[:150]}")
        return None
    except Exception as e:
        log.error(f"GET {path} → {e}")
        return None

def api_post(path: str, payload: dict | None = None) -> dict | None:
    url = f"{API_BASE}{path}"
    try:
        if payload is not None:
            r = requests.post(url, headers=_headers(with_body=True), json=payload, timeout=30)
        else:
            r = requests.post(url, headers=_headers(), timeout=30)
        log.debug(f"POST {path} → {r.status_code}: {r.text[:150]}")
        if r.status_code in (200, 201):
            return r.json()
        # Error handling dengan detail
        return {"_error": True, "_status": r.status_code, "_body": r.text[:300]}
    except Exception as e:
        log.error(f"POST {path} → {e}")
        return None


# ─── STEP 1: Buat Battle ─────────────────────────────────────────────────────
def create_battle() -> dict | None:
    """
    POST /api/deploy/battle
    Payload verified dari HAR:
      agent1Id   → UUID agent kamu
      rounds     → 5
      language   → "en"
      visibility → "public"

    Response 201:
      {"success": true, "battle": {"id": "UUID", "battleNumber": 85327, ...}}
    """
    payload = {
        "agent1Id":   AGENT_ID,
        "rounds":     ROUNDS,
        "language":   "en",
        "visibility": "public",
    }
    log.info(f"  📤 Step 1: POST /api/deploy/battle")
    return api_post("/deploy/battle", payload)


# ─── STEP 2: Run Battle ──────────────────────────────────────────────────────
def run_battle(battle_id: str) -> dict | None:
    """
    POST /api/battles/{id}/run  (no body)
    Response 200:
      {"success": true, "battleId": "...", "status": "active",
       "message": "Battle started in background. Watch for realtime updates."}
    """
    log.info(f"  ▶️  Step 2: POST /api/battles/{battle_id}/run")
    return api_post(f"/battles/{battle_id}/run")


# ─── STEP 3: Poll Hasil ──────────────────────────────────────────────────────
def poll_battle(battle_id: str, max_wait: int = 300) -> dict | None:
    """
    GET /api/battles/{id}
    Status flow: active → voting → completed
    Poll tiap 15 detik.

    Response: {"battle": {"status": "...", "winnerId": "...", ...}}
    """
    log.info(f"  🔄 Step 3: Polling GET /api/battles/{battle_id}")
    path     = f"/battles/{battle_id}"
    done     = {"completed", "finished", "done", "ended"}
    elapsed  = 0
    interval = 15

    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval

        data = api_get(path)
        if not data:
            log.warning(f"  ⚠️  Polling gagal ({elapsed}s elapsed), retry...")
            continue

        battle = data.get("battle", data)
        status = str(battle.get("status", "")).lower()
        cur_r  = battle.get("currentRound", "?")

        log.info(f"  ⌛ Status: [{status.upper()}] | Round: {cur_r}/{ROUNDS} | {elapsed}s elapsed")

        if status in done:
            log.info("  ✅ Battle selesai!")
            return battle
        if status == "voting":
            log.info("  🗳️  Masuk fase voting (battle selesai)!")
            return battle

    log.warning(f"  ⚠️  Polling timeout ({max_wait}s), lanjut cooldown...")
    return None


# ─── Tampilkan Hasil Battle ──────────────────────────────────────────────────
def print_result(battle: dict):
    if not battle:
        return
    bid      = battle.get("id", "?")
    bnum     = battle.get("battleNumber", "?")
    status   = battle.get("status", "?")
    topic    = battle.get("topic", "?")
    agent_a  = (battle.get("agentA") or {})
    agent_b  = (battle.get("agentB") or {})
    name_a   = agent_a.get("name", agent_a.get("displayName", "Agent A"))
    name_b   = agent_b.get("name", agent_b.get("displayName", "Agent B"))
    winner_id = battle.get("winnerId")
    vote_a   = battle.get("voteCountA", 0)
    vote_b   = battle.get("voteCountB", 0)
    url      = f"{BASE_URL}/battle/{bid}"

    log.info("  " + "─"*52)
    log.info(f"  🔥 BATTLE #{bnum} — {topic}")
    log.info(f"  ⚔️  {name_a}  vs  {name_b}")
    log.info(f"  🗳️  Votes  : {name_a}={vote_a} | {name_b}={vote_b}")
    if winner_id:
        winner = name_a if winner_id == agent_a.get("id") else name_b
        log.info(f"  🏆 Winner : {winner}")
    log.info(f"  📊 Status : {status}")
    log.info(f"  🔗 Link   : {url}")
    log.info("  " + "─"*52)


# ─── Countdown ───────────────────────────────────────────────────────────────
def countdown(seconds: int):
    log.info(f"\n  ⏳ Cooldown {seconds//60} menit {seconds%60} detik...\n")
    end      = time.time() + seconds
    next_log = time.time() + 60
    while time.time() < end:
        time.sleep(1)
        if time.time() >= next_log:
            rem  = int(end - time.time())
            m, s = divmod(rem, 60)
            log.info(f"  ⌛ Sisa: {m}m {s}s")
            next_log = time.time() + 60
    log.info("  ✅ Cooldown selesai! Siap battle lagi.\n")


# ─── Validasi Config ─────────────────────────────────────────────────────────
def validate():
    if not AGENT_ID:
        log.error("❌ MOLT_AGENT_ID belum diset di .env!")
        log.error("   Agent ID kamu: lihat URL https://moltarena.crosstoken.io/agents/AGENT-ID-DI-SINI")
        sys.exit(1)
    log.info(f"  🤖 Agent  : {AGENT_ID}")
    log.info(f"  🎯 Rounds : {ROUNDS}")
    log.info(f"  ⏱  Delay  : {DELAY_SEC}s ({DELAY_SEC//60} menit)")
    log.info(f"  🔄 Max    : {'∞ infinite' if MAX_BATTLES == 0 else f'{MAX_BATTLES} battles'}")


# ─── Main Loop ───────────────────────────────────────────────────────────────
def main(max_override: int = None):
    max_b = max_override if max_override is not None else MAX_BATTLES

    log.info("=" * 58)
    log.info("  🥊 MoltArena Auto Battle Bot v4 (FINAL)")
    log.info("  Mode: 1v1 Roast | Random Match | English")
    log.info("  Auth: Tidak perlu token — agent1Id saja!")
    log.info("=" * 58 + "\n")

    validate()

    count = 0
    log.info("🚀 Loop battle dimulai!\n")

    while True:
        count += 1
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.info(f"{'='*58}")
        log.info(f"  ⚔️  Battle ke-{count}  |  {now}")
        log.info(f"{'='*58}")

        # ── Step 1: Buat battle ────────────────────────────────────
        r1 = create_battle()

        if r1 is None:
            log.warning("  ⚠️  Tidak bisa connect, skip ke cooldown...")
        elif r1.get("_error"):
            s = r1["_status"]
            b = r1.get("_body","")
            log.warning(f"  ⚠️  HTTP {s}: {b[:150]}")
            if s == 429:
                log.warning("  🚦 Rate limit — tunggu 2 menit extra...")
                time.sleep(120)
        else:
            # Sukses ambil battle
            battle_raw = r1.get("battle", r1)
            battle_id  = battle_raw.get("id") or r1.get("battleId")
            bnum       = battle_raw.get("battleNumber", "?")
            topic      = battle_raw.get("topic", "?")

            log.info(f"  ✅ Battle #{bnum} dibuat! ID: {battle_id}")
            log.info(f"  📌 Topic: {topic}")

            if battle_id:
                # ── Step 2: Run battle ────────────────────────────
                time.sleep(2)
                r2 = run_battle(battle_id)
                if r2 and not r2.get("_error"):
                    log.info(f"  ✅ {r2.get('message', 'Battle berjalan!')}")
                else:
                    log.warning("  ⚠️  Run endpoint gagal, tetap lanjut polling...")

                # ── Step 3: Poll sampai selesai ───────────────────
                time.sleep(5)
                result = poll_battle(battle_id, max_wait=300)
                print_result(result or battle_raw)
            else:
                log.warning(f"  ⚠️  Tidak dapat battle_id: {json.dumps(r1)[:150]}")

        # ── Cek batas max ──────────────────────────────────────────
        if max_b > 0 and count >= max_b:
            log.info(f"\n✅ Selesai! Target {max_b} battles tercapai.")
            break

        countdown(DELAY_SEC)

    log.info(f"\n🏁 Bot selesai. Total: {count} battles")


# ─── Entry Point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    p = argparse.ArgumentParser(description="MoltArena Auto Battle Bot v4")
    p.add_argument("--once",  action="store_true", help="Jalankan 1 battle saja (test)")
    p.add_argument("--debug", action="store_true", help="Tampilkan HTTP log detail")
    args = p.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        main(max_override=1 if args.once else None)
    except KeyboardInterrupt:
        log.info("\n\n⛔ Dihentikan (Ctrl+C). Bye!")
        sys.exit(0)
