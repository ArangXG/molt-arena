#!/usr/bin/env python3
"""
MoltArena Auto Battle Bot — v7 (FINAL)
========================================
AUTH OPTIONS (pilih salah satu, prioritas dari atas):

  [1] API Key      → PALING MUDAH, tidak pernah expired
                     Dari: moltarena.crosstoken.io/settings/api
                     Set: MOLT_API_KEY=pk_live_...

  [2] Auto-refresh → Bot otomatis refresh token tiap 55 menit
                     Perlu: MOLT_REFRESH_TOKEN (ambil 1x dari browser)
                     Set: MOLT_REFRESH_TOKEN=...
                     Cara dapat:
                       F12 → Network → cari request ke supabase.co/auth/v1/token
                       → Response → copy refresh_token

  [3] Cookie       → Manual, expired tiap ~1 jam (tidak disarankan untuk auto-loop)
                     Set: MOLT_COOKIE=sb-...=...; sb-...=...

FLOW BATTLE (verified dari HAR):
  Step 1 → POST /api/deploy/battle   {agent1Id, rounds, language, visibility}
  Step 2 → POST /api/battles/{id}/run
  Step 3 → GET  /api/battles/{id}    poll tiap 15 detik
  Delay  → 10 menit → ulangi
"""

import os, sys, time, json, logging, argparse, requests, threading
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# ─── Supabase constants (dari HAR) ────────────────────────────
SUPABASE_URL    = "https://hkxnuxudaopdpmlcfqjf.supabase.co"
SUPABASE_APIKEY = "sb_publishable_tYf7a0a7sk3oJIljWKpIOg_zVxBYyNJ"
TOKEN_REFRESH_INTERVAL = 55 * 60   # refresh tiap 55 menit (expire 60 menit)

BASE_URL = "https://moltarena.crosstoken.io"
API_BASE = f"{BASE_URL}/api"
ENV_PATH = Path(__file__).parent / ".env"

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


# ─── Config ───────────────────────────────────────────────────
def load_config() -> dict:
    load_dotenv(ENV_PATH, override=True)
    return {
        "agent_id":      os.getenv("MOLT_AGENT_ID",          ""),
        "api_key":       os.getenv("MOLT_API_KEY",            ""),
        "refresh_token": os.getenv("MOLT_REFRESH_TOKEN",      ""),
        "cookie":        os.getenv("MOLT_COOKIE",             ""),
        "access_token":  os.getenv("MOLT_ACCESS_TOKEN",       ""),  # hasil auto-refresh
        "delay":         int(os.getenv("MOLT_DELAY_SECONDS",  "600")),
        "max_battles":   int(os.getenv("MOLT_MAX_BATTLES",    "0")),
        "rounds":        int(os.getenv("MOLT_ROUNDS",         "5")),
    }

cfg = load_config()


# ─── .env helper ──────────────────────────────────────────────
def update_env(key: str, value: str):
    """Update satu key di .env tanpa mengubah yang lain."""
    if not ENV_PATH.exists():
        ENV_PATH.write_text(f"{key}={value}\n")
        return
    lines = ENV_PATH.read_text().splitlines()
    new_lines, found = [], False
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n")


# ─── Supabase Auto-Refresh ────────────────────────────────────
def supabase_refresh(refresh_token: str) -> dict | None:
    """
    Hit Supabase refresh endpoint (dari HAR):
    POST https://hkxnuxudaopdpmlcfqjf.supabase.co/auth/v1/token?grant_type=refresh_token
    """
    try:
        r = requests.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
            headers={
                "apikey":       SUPABASE_APIKEY,
                "content-type": "application/json",
                "x-client-info": "supabase-ssr/0.8.0 createBrowserClient",
            },
            json={"refresh_token": refresh_token},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
        log.error(f"  Supabase refresh gagal: {r.status_code} {r.text[:150]}")
        return None
    except Exception as e:
        log.error(f"  Supabase refresh error: {e}")
        return None


def do_token_refresh() -> bool:
    """Refresh access token dan simpan ke .env + cfg. Return True jika sukses."""
    global cfg
    rt = cfg.get("refresh_token", "")
    if not rt:
        return False

    log.info("  🔄 Auto-refresh Supabase token...")
    data = supabase_refresh(rt)
    if not data:
        return False

    new_access  = data.get("access_token",  "")
    new_refresh = data.get("refresh_token", rt)  # Supabase kadang rotate refresh token

    if not new_access:
        return False

    # Simpan ke .env dan update cfg
    update_env("MOLT_ACCESS_TOKEN",  new_access)
    update_env("MOLT_REFRESH_TOKEN", new_refresh)
    cfg = load_config()

    expires_in = data.get("expires_in", 3600)
    log.info(f"  ✅ Token berhasil di-refresh! Expire dalam {expires_in//60} menit")
    return True


# ─── Background Token Refresh Thread ─────────────────────────
_stop_refresh = threading.Event()

def _refresh_loop():
    """Thread background: refresh token tiap 55 menit."""
    while not _stop_refresh.wait(TOKEN_REFRESH_INTERVAL):
        if cfg.get("refresh_token"):
            do_token_refresh()

def start_refresh_thread():
    t = threading.Thread(target=_refresh_loop, daemon=True, name="TokenRefresher")
    t.start()
    log.info("  🔄 Auto-refresh thread aktif (tiap 55 menit)")
    return t


# ─── Auth Header ──────────────────────────────────────────────
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

    # Prioritas auth: API Key > Access Token (auto-refresh) > Cookie
    if cfg.get("api_key"):
        h["authorization"] = f"Bearer {cfg['api_key']}"
    elif cfg.get("access_token"):
        h["authorization"] = f"Bearer {cfg['access_token']}"
    elif cfg.get("cookie"):
        h["cookie"] = cfg["cookie"]

    return h


# ─── HTTP ─────────────────────────────────────────────────────
def api_get(path: str) -> dict | None:
    try:
        r = requests.get(f"{API_BASE}{path}", headers=_headers(), timeout=30)
        if r.status_code == 200:
            return r.json()
        log.error(f"GET {path} → {r.status_code}: {r.text[:150]}")
        return None
    except Exception as e:
        log.error(f"GET {path} → {e}")
        return None

def api_post(path: str, payload: dict | None = None) -> dict | None:
    try:
        kw = {"headers": _headers(payload is not None), "timeout": 30}
        if payload is not None:
            kw["json"] = payload
        r = requests.post(f"{API_BASE}{path}", **kw)
        if r.status_code in (200, 201):
            return r.json()
        return {"_error": True, "_status": r.status_code, "_body": r.text[:300]}
    except Exception as e:
        log.error(f"POST {path} → {e}")
        return None


# ─── Handle 401 ───────────────────────────────────────────────
def handle_auth_error() -> bool:
    """
    Dipanggil saat 401/403.
    Coba auto-refresh dulu. Jika gagal, pause & minta input manual.
    Return True jika auth berhasil diperbaiki.
    """
    global cfg

    # Coba auto-refresh dulu jika ada refresh_token
    if cfg.get("refresh_token"):
        log.warning("  🔐 401 detected — mencoba auto-refresh token...")
        if do_token_refresh():
            return True
        log.error("  ❌ Auto-refresh gagal. Refresh token mungkin sudah invalid.")

    # Tidak bisa auto-refresh — pause & minta input
    log.error("━" * 58)
    log.error("  🔐 AUTH EXPIRED — Bot di-PAUSE")
    log.error("━" * 58)

    auth_mode = "API Key" if cfg.get("api_key") else ("Auto-refresh" if cfg.get("refresh_token") else "Cookie")
    log.error(f"  Mode auth saat ini: {auth_mode}")
    log.error("")
    log.error("  Pilih solusi:")
    log.error("  [1] Input API Key baru    (pk_live_... dari settings/api)")
    log.error("  [2] Input Refresh Token   (auto-refresh otomatis)")
    log.error("  [3] Input Cookie baru     (manual, expired ~1jam)")
    log.error("  [4] Keluar")
    log.error("━" * 58)

    while True:
        try:
            choice = input("\n  Pilih [1/2/3/4]: ").strip()
        except EOFError:
            # Non-interaktif (systemd/screen tanpa TTY)
            log.error("  ⚠️  Bot jalan non-interaktif, tidak bisa input.")
            log.error(f"  Update manual: nano {ENV_PATH}")
            log.error("  Lalu restart: sudo systemctl restart molt-battle")
            log.error("  Bot stop dalam 60 detik...")
            time.sleep(60)
            return False

        if choice == "1":
            val = input("  API Key (pk_live_...): ").strip()
            if val.startswith("pk_live_"):
                update_env("MOLT_API_KEY",       val)
                update_env("MOLT_ACCESS_TOKEN",  "")
                update_env("MOLT_REFRESH_TOKEN", "")
                update_env("MOLT_COOKIE",        "")
                cfg = load_config()
                log.info("  ✅ API Key diperbarui! Melanjutkan...")
                return True
            log.warning("  Harus dimulai 'pk_live_'")

        elif choice == "2":
            val = input("  Refresh Token: ").strip()
            if val:
                update_env("MOLT_REFRESH_TOKEN", val)
                update_env("MOLT_API_KEY",       "")
                update_env("MOLT_COOKIE",        "")
                cfg = load_config()
                log.info("  🔄 Mencoba refresh dengan token baru...")
                if do_token_refresh():
                    start_refresh_thread()  # restart background thread
                    return True
                log.error("  ❌ Refresh token tidak valid.")
            else:
                log.warning("  Tidak boleh kosong.")

        elif choice == "3":
            val = input("  Cookie: ").strip()
            if val:
                update_env("MOLT_COOKIE",        val)
                update_env("MOLT_API_KEY",       "")
                update_env("MOLT_ACCESS_TOKEN",  "")
                update_env("MOLT_REFRESH_TOKEN", "")
                cfg = load_config()
                log.info("  ✅ Cookie diperbarui! (ingat: expire ~1jam)")
                return True
            log.warning("  Tidak boleh kosong.")

        elif choice == "4":
            log.info("  👋 Bot dihentikan.")
            return False


# ─── Battle Steps ─────────────────────────────────────────────
def create_battle() -> dict | None:
    log.info("  📤 Step 1: POST /api/deploy/battle")
    return api_post("/deploy/battle", {
        "agent1Id":   cfg["agent_id"],
        "rounds":     cfg["rounds"],
        "language":   "en",
        "visibility": "public",
    })

def run_battle(battle_id: str) -> dict | None:
    log.info(f"  ▶️  Step 2: POST /api/battles/{battle_id}/run")
    return api_post(f"/battles/{battle_id}/run")

def poll_battle(battle_id: str) -> dict | None:
    log.info("  🔄 Step 3: Polling hasil...")
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
        log.info(f"  ⌛ [{status.upper()}] Round {battle.get('currentRound','?')}/{cfg['rounds']} | {elapsed}s")
        if status in done:
            return battle
    log.warning("  ⚠️  Timeout polling")
    return None

def print_result(battle: dict):
    if not battle:
        return
    a, b = battle.get("agentA") or {}, battle.get("agentB") or {}
    na, nb = a.get("name","Agent A"), b.get("name","Agent B")
    winner_id = battle.get("winnerId")
    log.info("  " + "─"*52)
    log.info(f"  🔥 Battle #{battle.get('battleNumber','?')} — {battle.get('topic','?')}")
    log.info(f"  ⚔️  {na}  vs  {nb}")
    if winner_id:
        log.info(f"  🏆 Winner: {'  '+na if winner_id==a.get('id') else nb}")
    log.info(f"  🗳️  Votes: {na}={battle.get('voteCountA',0)} | {nb}={battle.get('voteCountB',0)}")
    log.info(f"  🔗 {BASE_URL}/battle/{battle.get('id','?')}")
    log.info("  " + "─"*52)

def countdown(seconds: int):
    log.info(f"\n  ⏳ Cooldown {seconds//60}m {seconds%60}s...\n")
    end, next_log = time.time()+seconds, time.time()+60
    while time.time() < end:
        time.sleep(1)
        if time.time() >= next_log:
            rem = int(end - time.time())
            log.info(f"  ⌛ Sisa: {rem//60}m {rem%60}s")
            next_log = time.time()+60
    log.info("  ✅ Cooldown selesai!\n")


# ─── Validasi & Setup ─────────────────────────────────────────
def validate():
    errs = []
    if not cfg["agent_id"]:
        errs.append("MOLT_AGENT_ID belum diset")
    if not any([cfg["api_key"], cfg["refresh_token"], cfg["cookie"]]):
        errs.append(
            "Auth belum diset! Isi salah satu di .env:\n"
            "  MOLT_API_KEY=pk_live_...       ← paling mudah\n"
            "  MOLT_REFRESH_TOKEN=...         ← auto-refresh\n"
            "  MOLT_COOKIE=sb-...             ← manual"
        )
    if errs:
        for e in errs: log.error(f"❌ {e}")
        sys.exit(1)


def show_auth_mode():
    if cfg["api_key"]:
        masked = cfg["api_key"][:12] + "..." + cfg["api_key"][-4:]
        log.info(f"  🔑 Auth: API Key ({masked}) — tidak expired ✅")
    elif cfg["refresh_token"]:
        log.info("  🔑 Auth: Auto-refresh Supabase token (refresh tiap 55 menit) ✅")
    elif cfg["cookie"]:
        log.info("  🔑 Auth: Cookie — ⚠️  expire ~1jam, disarankan pakai API Key")


# ─── Main ─────────────────────────────────────────────────────
def main(max_override: int = None):
    global cfg
    max_b = max_override if max_override is not None else cfg["max_battles"]

    log.info("=" * 58)
    log.info("  🥊 MoltArena Auto Battle Bot v7")
    log.info("  Mode: 1v1 Roast | Random Match | English")
    log.info("=" * 58 + "\n")

    validate()
    show_auth_mode()
    log.info(f"  🤖 Agent  : {cfg['agent_id']}")
    log.info(f"  🎯 Rounds : {cfg['rounds']}")
    log.info(f"  ⏱  Delay  : {cfg['delay']}s ({cfg['delay']//60} menit)")
    log.info(f"  🔄 Max    : {'∞ infinite' if max_b==0 else f'{max_b} battles'}\n")

    # Jika pakai refresh token: lakukan refresh pertama & start background thread
    if cfg["refresh_token"] and not cfg["api_key"]:
        log.info("  🔄 Refresh token pertama...")
        if not do_token_refresh():
            log.error("  ❌ Refresh token tidak valid! Cek MOLT_REFRESH_TOKEN di .env")
            sys.exit(1)
        start_refresh_thread()

    count = 0
    log.info("🚀 Loop battle dimulai!\n")

    while True:
        count += 1
        log.info(f"{'='*58}")
        log.info(f"  ⚔️  Battle ke-{count}  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log.info(f"{'='*58}")

        r1 = create_battle()

        if r1 is None:
            log.warning("  ⚠️  Koneksi gagal, retry di cooldown berikutnya...")

        elif r1.get("_error"):
            s = r1["_status"]
            if s in (401, 403):
                ok = handle_auth_error()
                if not ok:
                    break
                count -= 1   # retry battle ini
                continue
            elif s == 429:
                log.warning("  🚦 Rate limit — tunggu 2 menit extra...")
                time.sleep(120)
            else:
                log.warning(f"  ⚠️  HTTP {s}: {r1.get('_body','')[:150]}")

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
                elif r2 and r2.get("_status") in (401, 403):
                    ok = handle_auth_error()
                    if not ok:
                        break
                    count -= 1
                    continue
                else:
                    log.warning("  ⚠️  /run gagal, tetap polling...")

                time.sleep(5)
                result = poll_battle(battle_id)
                print_result(result or battle_raw)

        if max_b > 0 and count >= max_b:
            log.info(f"\n✅ Selesai! {max_b} battles tercapai.")
            break

        countdown(cfg["delay"])

    _stop_refresh.set()
    log.info(f"\n🏁 Bot selesai. Total: {count} battles")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="MoltArena Auto Battle Bot v7")
    p.add_argument("--once",  action="store_true", help="1 battle saja (test)")
    p.add_argument("--debug", action="store_true", help="Log HTTP detail")
    args = p.parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    try:
        main(max_override=1 if args.once else None)
    except KeyboardInterrupt:
        _stop_refresh.set()
        log.info("\n\n⛔ Dihentikan (Ctrl+C). Bye!")
        sys.exit(0)
