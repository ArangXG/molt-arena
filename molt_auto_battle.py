#!/usr/bin/env python3
"""
MoltArena Auto Battle Bot — v9
======================================
- API Key only, fully automatic, zero user interaction
- /deploy/battle      → pakai Authorization: Bearer <api_key>
- /battles/{id}/run   → tanpa auth (verified dari HAR browser)
- /battles/{id}       → tanpa auth (GET public)
- /battles/{id}/vote  → AUTO VOTE untuk agent sendiri saat sesi voting
- Win/loss ditampilkan jelas
- Summary otomatis saat Ctrl+C
"""

import os, sys, time, json, logging, argparse, signal
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(ENV_PATH)

BASE_URL = "https://moltarena.crosstoken.io"
API_BASE = f"{BASE_URL}/api"

# ─── Config ───────────────────────────────────────────────────
AGENT_ID    = os.getenv("MOLT_AGENT_ID",          "")
API_KEY     = os.getenv("MOLT_API_KEY",            "")
DELAY_SEC   = int(os.getenv("MOLT_DELAY_SECONDS",  "600"))
MAX_BATTLES = int(os.getenv("MOLT_MAX_BATTLES",    "0"))
ROUNDS      = int(os.getenv("MOLT_ROUNDS",         "5"))
AUTO_VOTE   = os.getenv("MOLT_AUTO_VOTE",          "true").lower() not in ("0", "false", "no")

# ─── Session Stats (untuk summary) ────────────────────────────
stats = {
    "start_time": datetime.now(),
    "total":      0,
    "win":        0,
    "lose":       0,
    "draw":       0,
    "skip":       0,   # error/timeout
    "voted":      0,   # berhasil auto-vote
    "battles":    [],  # list detail tiap battle
}

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


# ─── Headers helper ───────────────────────────────────────────
def _h_auth() -> dict:
    """Header dengan API Key — untuk /deploy/battle."""
    return {
        "accept":          "*/*",
        "accept-language": "en-US,en;q=0.9",
        "content-type":    "application/json",
        "authorization":   f"Bearer {API_KEY}",
        "origin":          BASE_URL,
        "referer":         f"{BASE_URL}/battles/new",
        "user-agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

def _h_noauth() -> dict:
    """Header tanpa auth — untuk /run dan GET (verified HAR)."""
    return {
        "accept":          "*/*",
        "accept-language": "en-US,en;q=0.9",
        "origin":          BASE_URL,
        "referer":         f"{BASE_URL}/battles/new",
        "user-agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }


# ─── HTTP ─────────────────────────────────────────────────────
def api_get(path: str) -> dict | None:
    try:
        r = requests.get(f"{API_BASE}{path}", headers=_h_noauth(), timeout=30)
        if r.status_code == 200:
            return r.json()
        log.error(f"GET {path} → {r.status_code}: {r.text[:100]}")
        return None
    except Exception as e:
        log.error(f"GET {path} → {e}")
        return None

def api_post_auth(path: str, payload: dict) -> dict | None:
    """POST dengan API Key auth — Step 1."""
    try:
        r = requests.post(f"{API_BASE}{path}", headers=_h_auth(), json=payload, timeout=30)
        log.debug(f"POST {path} → {r.status_code}")
        if r.status_code in (200, 201):
            return r.json()
        return {"_error": True, "_status": r.status_code, "_body": r.text[:300]}
    except Exception as e:
        log.error(f"POST {path} → {e}")
        return None

def api_post_noauth(path: str) -> dict | None:
    """POST tanpa auth, tanpa body — Step 2 /run (verified HAR)."""
    try:
        h = {**_h_noauth(), "content-length": "0"}
        r = requests.post(f"{API_BASE}{path}", headers=h, timeout=30)
        log.debug(f"POST {path} → {r.status_code}")
        if r.status_code in (200, 201):
            return r.json()
        return {"_error": True, "_status": r.status_code, "_body": r.text[:300]}
    except Exception as e:
        log.error(f"POST {path} → {e}")
        return None


# ─── Battle Steps ─────────────────────────────────────────────
def step1_create() -> dict | None:
    """POST /api/deploy/battle dengan API Key."""
    return api_post_auth("/deploy/battle", {
        "agent1Id":   AGENT_ID,
        "rounds":     ROUNDS,
        "language":   "en",
        "visibility": "public",
    })

def step2_run(battle_id: str) -> bool:
    """POST /api/battles/{id}/run tanpa auth (verified HAR)."""
    r = api_post_noauth(f"/battles/{battle_id}/run")
    if r and not r.get("_error"):
        return True
    # Jika masih 401, coba dengan auth juga
    if r and r.get("_status") == 401:
        log.debug("  /run 401 tanpa auth, coba dengan auth...")
        r2 = api_post_auth(f"/battles/{battle_id}/run", {})
        return bool(r2 and not r2.get("_error"))
    return False

def step4_vote(battle_id: str, agent_id: str) -> bool:
    """POST /api/battles/{id}/vote untuk vote agent sendiri (verified HAR, tanpa auth)."""
    if not AUTO_VOTE:
        return False
    try:
        h = {**_h_noauth(), "content-type": "application/json"}
        r = requests.post(
            f"{API_BASE}/battles/{battle_id}/vote",
            headers=h,
            json={"agentId": agent_id},
            timeout=15,
        )
        if r.status_code in (200, 201):
            data = r.json()
            weight = data.get("vote", {}).get("voteWeight", "?")
            counts = data.get("voteCounts", {})
            log.info(f"  🗳️  Auto-vote berhasil! Weight={weight} | Votes={counts}")
            stats["voted"] += 1
            return True
        elif r.status_code == 409:
            log.info("  🗳️  Sudah pernah vote di battle ini (skip).")
            return False
        else:
            log.warning(f"  ⚠️  Vote gagal HTTP {r.status_code}: {r.text[:100]}")
            return False
    except Exception as e:
        log.error(f"  Vote error: {e}")
        return False


def step3_poll(battle_id: str) -> dict | None:
    """GET /api/battles/{id} tiap 15 detik sampai selesai."""
    done = {"completed", "finished", "done", "ended", "voting"}
    elapsed, max_wait = 0, 300
    while elapsed < max_wait:
        time.sleep(15)
        elapsed += 15
        data = api_get(f"/battles/{battle_id}")
        if not data:
            continue
        battle = data.get("battle", data)
        status = str(battle.get("status", "")).lower()
        cur_r  = battle.get("currentRound", "?")
        log.info(f"  ⌛ [{status.upper()}] Round {cur_r}/{ROUNDS} | +{elapsed}s")
        if status in done:
            # Langsung vote saat status 'voting' terdeteksi
            if status == "voting":
                log.info("  🗳️  Status VOTING terdeteksi → auto-vote...")
                step4_vote(battle_id, AGENT_ID)
            return battle
    return None


# ─── Tampilkan Hasil ──────────────────────────────────────────
def show_result(battle: dict, my_agent_id: str) -> str:
    """Tampilkan hasil battle dengan jelas. Return 'win'/'lose'/'draw'."""
    if not battle:
        return "skip"

    agent_a   = battle.get("agentA") or {}
    agent_b   = battle.get("agentB") or {}
    name_a    = agent_a.get("name", "Agent A")
    name_b    = agent_b.get("name", "Agent B")
    id_a      = agent_a.get("id", "")
    id_b      = agent_b.get("id", "")
    winner_id = battle.get("winnerId")
    vote_a    = battle.get("voteCountA", 0)
    vote_b    = battle.get("voteCountB", 0)
    topic     = battle.get("topic", "?")
    bnum      = battle.get("battleNumber", "?")
    url       = f"{BASE_URL}/battle/{battle.get('id','?')}"

    # Tentukan menang/kalah
    my_name = name_a if my_agent_id == id_a else name_b
    op_name = name_b if my_agent_id == id_a else name_a

    if winner_id is None:
        outcome = "draw"
        icon    = "🤝"
        label   = "DRAW"
    elif winner_id == my_agent_id:
        outcome = "win"
        icon    = "🏆"
        label   = "MENANG"
    else:
        outcome = "lose"
        icon    = "💀"
        label   = "KALAH"

    log.info("")
    log.info("  ╔══════════════════════════════════════════════════╗")
    log.info(f"  ║  {icon}  HASIL BATTLE #{bnum:<6}  →  {label:<6}            ║")
    log.info("  ╠══════════════════════════════════════════════════╣")
    log.info(f"  ║  📌 Topic   : {topic[:40]:<40}  ║")
    log.info(f"  ║  ⚔️  {my_name[:12]:<12} vs {op_name[:12]:<12}                   ║")
    log.info(f"  ║  🗳️  Votes   : {my_name[:8]:<8}={vote_a if my_agent_id==id_a else vote_b}  |  {op_name[:8]:<8}={vote_b if my_agent_id==id_a else vote_a}       ║")
    log.info(f"  ║  🔗 {url[:46]:<46}  ║")
    log.info("  ╚══════════════════════════════════════════════════╝")
    log.info("")
    return outcome


# ─── Summary ──────────────────────────────────────────────────
def print_summary():
    elapsed = datetime.now() - stats["start_time"]
    hours, rem = divmod(int(elapsed.total_seconds()), 3600)
    mins, secs = divmod(rem, 60)
    total = stats["total"]
    win   = stats["win"]
    lose  = stats["lose"]
    draw  = stats["draw"]
    skip  = stats["skip"]
    wr    = f"{win/total*100:.1f}%" if total > 0 else "N/A"

    log.info("")
    log.info("  ╔══════════════════════════════════════════════════╗")
    log.info("  ║          📊  SESSION SUMMARY                     ║")
    log.info("  ╠══════════════════════════════════════════════════╣")
    log.info(f"  ║  ⏱️  Durasi      : {hours}j {mins}m {secs}s{'':<25}║")
    log.info(f"  ║  ⚔️  Total Battle: {total:<32}║")
    log.info(f"  ║  🏆 Menang      : {win:<32}║")
    log.info(f"  ║  💀 Kalah       : {lose:<32}║")
    log.info(f"  ║  🤝 Draw        : {draw:<32}║")
    log.info(f"  ║  ⏭️  Skip/Error  : {skip:<32}║")
    log.info(f"  ║  🗳️  Auto-Vote   : {stats['voted']:<32}║")
    log.info(f"  ║  📈 Win Rate    : {wr:<32}║")
    log.info("  ╠══════════════════════════════════════════════════╣")

    if stats["battles"]:
        log.info("  ║  📋 Riwayat Battle:                              ║")
        for b in stats["battles"][-10:]:  # tampil max 10 terakhir
            icon = "🏆" if b["outcome"]=="win" else "💀" if b["outcome"]=="lose" else "🤝" if b["outcome"]=="draw" else "⏭️"
            log.info(f"  ║    {icon} #{b['num']:<6} vs {b['opponent'][:15]:<15} {b['outcome'].upper():<6}  ║")

    log.info("  ╚══════════════════════════════════════════════════╝")
    log.info("")


# ─── Countdown ────────────────────────────────────────────────
def countdown(seconds: int):
    log.info(f"  ⏳ Cooldown {seconds//60} menit {seconds%60} detik...")
    end = time.time() + seconds
    next_log = time.time() + 60
    while time.time() < end:
        time.sleep(1)
        if time.time() >= next_log:
            rem = int(end - time.time())
            log.info(f"  ⌛ Sisa cooldown: {rem//60}m {rem%60}s")
            next_log = time.time() + 60
    log.info("  ✅ Cooldown selesai! Mulai battle berikutnya...\n")


# ─── Validasi ─────────────────────────────────────────────────
def validate():
    errs = []
    if not AGENT_ID:
        errs.append("MOLT_AGENT_ID belum diset di .env")
    if not API_KEY:
        errs.append("MOLT_API_KEY belum diset di .env\n"
                    "  → Buka: moltarena.crosstoken.io/settings/api → Generate Key")
    elif not API_KEY.startswith("pk_live_"):
        errs.append("MOLT_API_KEY harus dimulai 'pk_live_'")
    if errs:
        for e in errs:
            log.error(f"❌ {e}")
        sys.exit(1)


# ─── Signal handler untuk summary ─────────────────────────────
def _on_exit(sig, frame):
    log.info("\n\n⛔ Bot dihentikan (Ctrl+C)\n")
    print_summary()
    sys.exit(0)


# ─── Main ─────────────────────────────────────────────────────
def main(max_override: int = None):
    max_b = max_override if max_override is not None else MAX_BATTLES

    signal.signal(signal.SIGINT,  _on_exit)
    signal.signal(signal.SIGTERM, _on_exit)

    log.info("==" * 29)
    log.info("  🥊 MoltArena Auto Battle Bot v9")
    log.info("  Mode  : 1v1 Roast | Auto-Vote | Random Match | English")
    log.info(f"  Auth  : API Key ({API_KEY[:12]}...{API_KEY[-4:]})")
    log.info(f"  Agent : {AGENT_ID}")
    log.info(f"  Rounds: {ROUNDS} | Delay: {DELAY_SEC//60}m | Max: {'∞' if max_b==0 else max_b}")
    log.info(f"  Vote  : {'✅ AUTO-VOTE AKTIF' if AUTO_VOTE else '❌ Dinonaktifkan (set MOLT_AUTO_VOTE=true)'}")
    log.info("==" * 29)

    validate()
    stats["start_time"] = datetime.now()

    log.info("🚀 Auto battle dimulai! (Ctrl+C untuk stop + lihat summary)\n")

    count = 0
    while True:
        count += 1
        stats["total"] = count
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log.info(f"{'─'*58}")
        log.info(f"  ⚔️  Battle ke-{count}  |  {now}")
        log.info(f"{'─'*58}")

        # ── STEP 1: Buat battle (dengan API Key) ──────────────
        log.info("  📤 Step 1: Buat battle...")
        r1 = step1_create()

        if not r1 or r1.get("_error"):
            s = (r1 or {}).get("_status", 0)
            b = (r1 or {}).get("_body", "Tidak ada response")
            if s in (401, 403):
                log.error(f"  ❌ API Key ditolak ({s}). Cek MOLT_API_KEY di .env")
                log.error("  → Buka: moltarena.crosstoken.io/settings/api → Generate Key baru")
                log.error("  → Bot berhenti. Update .env lalu jalankan ulang.")
                print_summary()
                sys.exit(1)
            elif s == 429:
                log.warning("  🚦 Rate limit. Tunggu 5 menit...")
                stats["skip"] += 1
                stats["total"] -= 1
                count -= 1
                time.sleep(300)
                continue
            else:
                log.warning(f"  ⚠️  Gagal buat battle (HTTP {s}). Skip, lanjut cooldown...")
                stats["skip"] += 1
                stats["battles"].append({"num":"?","opponent":"?","outcome":"skip"})
        else:
            # Battle berhasil dibuat
            battle_raw = r1.get("battle", r1)
            battle_id  = battle_raw.get("id") or r1.get("battleId","")
            bnum       = battle_raw.get("battleNumber","?")
            topic      = battle_raw.get("topic","?")
            agent_b    = (battle_raw.get("participants",{}).get("agent2") or
                         battle_raw.get("agentB") or {})
            opp_name   = agent_b.get("name", agent_b.get("displayName","Random"))

            log.info(f"  ✅ Battle #{bnum} dibuat!")
            log.info(f"  📌 Topic: {topic}")
            log.info(f"  🆚 Lawan: {opp_name}")

            # ── STEP 2: Run battle (tanpa auth, verified HAR) ──
            log.info(f"  ▶️  Step 2: Jalankan battle...")
            ok = step2_run(battle_id)
            if ok:
                log.info("  ✅ Battle berjalan! Menunggu hasil...")
            else:
                log.warning("  ⚠️  /run endpoint error, tetap polling...")

            # ── STEP 3: Poll hasil ─────────────────────────────
            log.info("  🔄 Step 3: Polling hasil battle...")
            time.sleep(5)
            result = step3_poll(battle_id)

            if result:
                outcome = show_result(result, AGENT_ID)
                # Fallback vote jika status bukan 'voting' tapi sudah selesai
                result_status = str(result.get("status", "")).lower()
                if result_status != "voting":
                    log.info("  🗳️  Battle selesai → mencoba auto-vote...")
                    step4_vote(battle_id, AGENT_ID)
            else:
                log.warning("  ⚠️  Polling timeout, hasil tidak didapat")
                outcome = "skip"

            # Update stats
            if outcome == "win":    stats["win"]  += 1
            elif outcome == "lose": stats["lose"] += 1
            elif outcome == "draw": stats["draw"] += 1
            else:                   stats["skip"] += 1

            stats["battles"].append({
                "num":      bnum,
                "opponent": opp_name,
                "outcome":  outcome,
            })

        # ── Cek batas max ──────────────────────────────────────
        if max_b > 0 and count >= max_b:
            log.info(f"\n✅ Target {max_b} battles tercapai.")
            break

        countdown(DELAY_SEC)

    print_summary()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="MoltArena Auto Battle Bot v8")
    p.add_argument("--once",  action="store_true", help="1 battle saja (test)")
    p.add_argument("--debug", action="store_true", help="Log HTTP detail")
    args = p.parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    main(max_override=1 if args.once else None)
