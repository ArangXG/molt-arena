#!/bin/bash
# MoltArena Auto Battle Bot v8 — Setup & Run
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BLUE='\033[0;34m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
MAIN_SCRIPT="$SCRIPT_DIR/molt_auto_battle.py"
VENV_DIR="$SCRIPT_DIR/venv"
LOG_FILE="$SCRIPT_DIR/molt_battle.log"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"

info()    { echo -e "  ${CYAN}ℹ️  $1${NC}"; }
success() { echo -e "  ${GREEN}✅ $1${NC}"; }
warn()    { echo -e "  ${YELLOW}⚠️  $1${NC}"; }
error()   { echo -e "  ${RED}❌ $1${NC}"; }
step()    { echo -e "\n${BOLD}${BLUE}▶ $1${NC}"; }
divider() { echo -e "${DIM}  ──────────────────────────────────────────────${NC}"; }

print_banner() {
    clear 2>/dev/null || true
    echo ""
    echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}${BOLD}║        🥊  MoltArena Auto Battle Bot v9  🥊              ║${NC}"
    echo -e "${CYAN}${BOLD}║   1v1 Roast | Auto Loop | Auto-Vote | Win/Lose Summary  ║${NC}"
    echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

check_python() {
    step "Cek Python..."
    if command -v python3 &>/dev/null; then
        success "$(python3 --version)"
        PYTHON_BIN="python3"
    else
        error "Python3 tidak ditemukan!"
        echo -e "  Install: ${YELLOW}sudo apt install python3 python3-pip python3-venv -y${NC}"
        exit 1
    fi
}

setup_venv() {
    step "Setup Virtual Environment..."
    [ ! -d "$VENV_DIR" ] && $PYTHON_BIN -m venv "$VENV_DIR" && info "venv baru dibuat"
    source "$VENV_DIR/bin/activate"
    PYTHON_BIN="$VENV_DIR/bin/python"
    PIP_BIN="$VENV_DIR/bin/pip"
    success "Virtual environment siap"
}

install_deps() {
    step "Install Dependencies..."
    $PIP_BIN install -q --upgrade pip
    [ -f "$REQUIREMENTS" ] && $PIP_BIN install -q -r "$REQUIREMENTS" \
        || $PIP_BIN install -q requests python-dotenv
    success "Dependencies siap"
}

create_env() {
    echo ""
    echo -e "${YELLOW}${BOLD}  📝 Setup Konfigurasi (hanya butuh API Key + Agent ID)${NC}"
    echo ""
    divider

    # ── API Key ───────────────────────────────────────────────
    echo ""
    echo -e "  ${BOLD}🔑 API Key${NC}"
    echo -e "  ${DIM}Buka: https://moltarena.crosstoken.io/settings/api${NC}"
    echo -e "  ${DIM}Klik Generate → copy key yang dimulai pk_live_...${NC}"
    echo ""
    while true; do
        echo -ne "  Paste API Key: "
        read -r INPUT_APIKEY
        INPUT_APIKEY=$(echo "$INPUT_APIKEY" | tr -d '[:space:]')
        if [[ "$INPUT_APIKEY" == pk_live_* ]] && [ ${#INPUT_APIKEY} -gt 10 ]; then
            success "API Key valid"
            break
        else
            warn "Harus dimulai 'pk_live_'. Coba lagi."
        fi
    done

    # ── Agent ID ──────────────────────────────────────────────
    echo ""
    echo -e "  ${BOLD}🤖 Agent ID${NC}"
    echo -e "  ${DIM}Lihat di URL: moltarena.crosstoken.io/agents/AGENT-ID-DI-SINI${NC}"
    echo ""
    while true; do
        echo -ne "  Paste Agent ID: "
        read -r INPUT_AGENT
        INPUT_AGENT=$(echo "$INPUT_AGENT" | tr -d '[:space:]')
        [ -n "$INPUT_AGENT" ] && { success "Agent ID: $INPUT_AGENT"; break; } \
            || warn "Tidak boleh kosong."
    done

    # ── Delay ─────────────────────────────────────────────────
    echo ""
    echo -ne "  ${BOLD}⏱  Delay antar battle (detik) [default 600 = 10 menit]: ${NC}"
    read -r INPUT_DELAY
    INPUT_DELAY=$(echo "$INPUT_DELAY" | tr -d '[:space:]')
    [[ "$INPUT_DELAY" =~ ^[0-9]+$ ]] || INPUT_DELAY=600
    info "Delay: ${INPUT_DELAY}s ($(( INPUT_DELAY / 60 )) menit)"

    # ── Max ───────────────────────────────────────────────────
    echo -ne "  ${BOLD}🔄 Max battle [0 = infinite]: ${NC}"
    read -r INPUT_MAX
    INPUT_MAX=$(echo "$INPUT_MAX" | tr -d '[:space:]')
    [[ "$INPUT_MAX" =~ ^[0-9]+$ ]] || INPUT_MAX=0
    [ "$INPUT_MAX" -eq 0 ] && info "Mode: ∞ infinite" || info "Max: $INPUT_MAX battles"

    # ── Rounds ────────────────────────────────────────────────
    echo -ne "  ${BOLD}🎯 Round per battle [3/5/7/10, default 5]: ${NC}"
    read -r INPUT_ROUNDS
    INPUT_ROUNDS=$(echo "$INPUT_ROUNDS" | tr -d '[:space:]')
    [[ "$INPUT_ROUNDS" =~ ^(3|5|7|10)$ ]] || INPUT_ROUNDS=5
    info "Rounds: $INPUT_ROUNDS"

    # ── Auto Vote ─────────────────────────────────────────────
    echo -ne "  ${BOLD}🗳️  Auto-Vote untuk diri sendiri? [Y/n]: ${NC}"
    read -r INPUT_VOTE
    INPUT_VOTE=$(echo "$INPUT_VOTE" | tr -d '[:space:]')
    [[ "$INPUT_VOTE" =~ ^[Nn]$ ]] && INPUT_VOTE="false" || INPUT_VOTE="true"
    [ "$INPUT_VOTE" = "true" ] && info "Auto-Vote: AKTIF ✅" || info "Auto-Vote: Nonaktif"

    # ── Tulis .env ────────────────────────────────────────────
    cat > "$ENV_FILE" <<ENVEOF
# MoltArena Auto Battle Bot v9 — Generated $(date '+%Y-%m-%d %H:%M:%S')

MOLT_API_KEY=${INPUT_APIKEY}
MOLT_AGENT_ID=${INPUT_AGENT}
MOLT_DELAY_SECONDS=${INPUT_DELAY}
MOLT_MAX_BATTLES=${INPUT_MAX}
MOLT_ROUNDS=${INPUT_ROUNDS}
MOLT_AUTO_VOTE=${INPUT_VOTE}
ENVEOF

    echo ""
    success ".env berhasil dibuat!"
}

show_config() {
    set -a; source "$ENV_FILE" 2>/dev/null; set +a
    step "Konfigurasi Aktif:"
    divider
    MASKED="${MOLT_API_KEY:0:12}...${MOLT_API_KEY: -4}"
    echo -e "  🔑 API Key : ${GREEN}${MASKED}${NC}"
    echo -e "  🤖 Agent   : ${CYAN}${MOLT_AGENT_ID}${NC}"
    echo -e "  🎯 Rounds  : ${CYAN}${MOLT_ROUNDS:-5}${NC}"
    echo -e "  🗳️  Auto-Vote: ${CYAN}${MOLT_AUTO_VOTE:-true}${NC}"
    echo -e "  ⏱  Delay   : ${CYAN}${MOLT_DELAY_SECONDS:-600}s ($(( ${MOLT_DELAY_SECONDS:-600} / 60 )) menit)${NC}"
    [ "${MOLT_MAX_BATTLES:-0}" -eq 0 ] \
        && echo -e "  🔄 Mode    : ${CYAN}∞ Infinite loop${NC}" \
        || echo -e "  🔄 Max     : ${CYAN}${MOLT_MAX_BATTLES} battles${NC}"
    divider
    echo ""
}

edit_env_menu() {
    echo ""
    echo -e "  ${BOLD}📝 File .env sudah ada.${NC}"
    echo ""
    echo -e "  ${CYAN}[1]${NC} Langsung jalankan"
    echo -e "  ${CYAN}[2]${NC} Setup ulang config"
    echo -e "  ${CYAN}[3]${NC} Ganti API Key saja"
    echo -e "  ${CYAN}[4]${NC} Lihat config"
    echo -e "  ${CYAN}[5]${NC} Keluar"
    echo ""
    echo -ne "  ${BOLD}Pilih [1-5]: ${NC}"
    read -r C
    case "$C" in
        1) return ;;
        2) rm -f "$ENV_FILE"; create_env ;;
        3)
            echo ""
            echo -ne "  ${BOLD}Paste API Key baru (pk_live_...): ${NC}"
            read -r NEW_KEY
            NEW_KEY=$(echo "$NEW_KEY" | tr -d '[:space:]')
            if [[ "$NEW_KEY" == pk_live_* ]]; then
                sed -i "s|^MOLT_API_KEY=.*|MOLT_API_KEY=${NEW_KEY}|" "$ENV_FILE"
                success "API Key diperbarui!"
            else
                warn "Format salah, tidak diubah."
            fi
            ;;
        4) show_config
           echo -ne "  Lanjut jalankan? [y/N]: "
           read -r X; [[ "$X" =~ ^[Yy]$ ]] || exit 0 ;;
        5) exit 0 ;;
        *) info "Melanjutkan..." ;;
    esac
}

choose_run_mode() {
    echo -e "${BOLD}  🚀 Cara menjalankan:${NC}"
    echo ""
    echo -e "  ${CYAN}[1]${NC} Test 1 battle  ${DIM}— verifikasi API Key & koneksi${NC}"
    echo -e "  ${CYAN}[2]${NC} Foreground      ${DIM}— Ctrl+C untuk stop + lihat summary${NC}"
    echo -e "  ${CYAN}[3]${NC} Screen          ${DIM}— background, tetap jalan walau SSH disconnect${NC}"
    echo -e "  ${CYAN}[4]${NC} Systemd         ${DIM}— auto-start saat server reboot${NC}"
    echo -e "  ${CYAN}[5]${NC} Keluar"
    echo ""
    echo -ne "  ${BOLD}Pilih [1-5]: ${NC}"
    read -r MODE
    case "$MODE" in
        1) run_test ;;
        2) run_foreground ;;
        3) run_screen ;;
        4) run_systemd ;;
        5) exit 0 ;;
        *) run_foreground ;;
    esac
}

run_test() {
    echo ""
    success "Test 1 battle (debug mode)..."
    echo ""
    source "$VENV_DIR/bin/activate"
    "$PYTHON_BIN" "$MAIN_SCRIPT" --once --debug
    echo ""
    echo -ne "  ${BOLD}Lanjut loop infinite? [y/N]: ${NC}"
    read -r C
    [[ "$C" =~ ^[Yy]$ ]] && run_foreground || exit 0
}

run_foreground() {
    echo ""
    success "Menjalankan... (Ctrl+C untuk stop & lihat summary)"
    echo ""
    source "$VENV_DIR/bin/activate"
    exec "$PYTHON_BIN" "$MAIN_SCRIPT"
}

run_screen() {
    step "Background dengan screen..."
    command -v screen &>/dev/null || sudo apt install screen -y
    SESSION="molt-bot"
    screen -S "$SESSION" -X quit 2>/dev/null || true
    sleep 1
    screen -dmS "$SESSION" bash -c "
        source '$VENV_DIR/bin/activate'
        '$PYTHON_BIN' '$MAIN_SCRIPT'
    "
    sleep 2
    if screen -list | grep -q "$SESSION"; then
        success "Bot berjalan di background!"
    else
        warn "Screen gagal, coba foreground"
        return
    fi
    echo ""
    divider
    echo -e "  ${CYAN}screen -r $SESSION${NC}              → Lihat log live"
    echo -e "  ${CYAN}Ctrl+A → D${NC}                    → Detach"
    echo -e "  ${CYAN}screen -S $SESSION -X quit${NC}      → Stop bot"
    echo -e "  ${CYAN}tail -f $LOG_FILE${NC}"
    divider
}

run_systemd() {
    step "Install sebagai systemd service..."
    CURRENT_USER=$(whoami)
    cat > /tmp/molt-battle.service <<SVCEOF
[Unit]
Description=MoltArena Auto Battle Bot v8
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${VENV_DIR}/bin/python ${MAIN_SCRIPT}
Restart=always
RestartSec=60
EnvironmentFile=${ENV_FILE}

[Install]
WantedBy=multi-user.target
SVCEOF
    sudo cp /tmp/molt-battle.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable molt-battle
    sudo systemctl restart molt-battle
    sleep 2
    STATUS=$(sudo systemctl is-active molt-battle)
    [ "$STATUS" = "active" ] && success "Service aktif!" || warn "Status: $STATUS"
    echo ""
    divider
    echo -e "  ${CYAN}sudo systemctl status molt-battle${NC}"
    echo -e "  ${CYAN}sudo journalctl -u molt-battle -f${NC}"
    echo -e "  ${CYAN}sudo systemctl restart molt-battle${NC}"
    echo -e "  ${CYAN}sudo systemctl stop molt-battle${NC}"
    divider
}

# ═══════════ MAIN ═══════════
print_banner
check_python
[ ! -f "$MAIN_SCRIPT" ] && { error "molt_auto_battle.py tidak ditemukan!"; exit 1; }
setup_venv
install_deps

step "Cek .env..."
if [ ! -f "$ENV_FILE" ]; then
    warn ".env tidak ditemukan → Membuat file baru..."
    create_env
else
    success ".env ditemukan"
    edit_env_menu
fi

show_config
choose_run_mode
