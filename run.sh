#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║       🥊 MoltArena Auto Battle Bot v4 — Setup & Run         ║
# ║  VERIFIED: Tidak perlu auth token, hanya butuh Agent ID!    ║
# ╚══════════════════════════════════════════════════════════════╝
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
divider() { echo -e "${DIM}  ────────────────────────────────────────────────${NC}"; }

print_banner() {
    echo ""
    echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}${BOLD}║        🥊  MoltArena Auto Battle Bot v4  🥊              ║${NC}"
    echo -e "${CYAN}${BOLD}║   1v1 Roast | Random | English | Loop 10 Menit          ║${NC}"
    echo -e "${CYAN}${BOLD}║   ✅ Verified — Tidak perlu token auth!                  ║${NC}"
    echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

check_python() {
    step "Cek Python..."
    if command -v python3 &>/dev/null; then
        success "$(python3 --version) ditemukan"
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
    success "Virtual environment siap"
    source "$VENV_DIR/bin/activate"
    PYTHON_BIN="$VENV_DIR/bin/python"
    PIP_BIN="$VENV_DIR/bin/pip"
}

install_deps() {
    step "Install Dependencies..."
    $PIP_BIN install -q --upgrade pip
    [ -f "$REQUIREMENTS" ] && $PIP_BIN install -q -r "$REQUIREMENTS" || $PIP_BIN install -q requests python-dotenv
    success "requests & python-dotenv siap"
}

check_script() {
    step "Cek script utama..."
    [ ! -f "$MAIN_SCRIPT" ] && { error "molt_auto_battle.py tidak ditemukan!"; exit 1; }
    success "molt_auto_battle.py ditemukan"
}

create_env() {
    echo ""
    echo -e "${YELLOW}${BOLD}  📝 Setup Konfigurasi — Hanya butuh Agent ID!${NC}"
    echo ""
    divider
    echo -e "  ${DIM}Agent ID ada di URL halaman agent kamu:${NC}"
    echo -e "  ${CYAN}  https://moltarena.crosstoken.io/agents/AGENT-ID-DI-SINI${NC}"
    divider
    echo ""

    # Agent ID
    while true; do
        echo -ne "  ${BOLD}🤖 Masukkan Agent ID kamu: ${NC}"
        read -r INPUT_AGENT
        INPUT_AGENT=$(echo "$INPUT_AGENT" | tr -d '[:space:]')
        if [ -n "$INPUT_AGENT" ]; then
            success "Agent ID: $INPUT_AGENT"
            break
        else
            warn "Agent ID tidak boleh kosong."
        fi
    done

    # Delay
    echo ""
    echo -ne "  ${BOLD}⏱  Delay antar battle detik [default 600 = 10 menit]: ${NC}"
    read -r INPUT_DELAY
    INPUT_DELAY=$(echo "$INPUT_DELAY" | tr -d '[:space:]')
    [[ "$INPUT_DELAY" =~ ^[0-9]+$ ]] || INPUT_DELAY=600
    info "Delay: ${INPUT_DELAY}s ($(( INPUT_DELAY / 60 )) menit)"

    # Max
    echo ""
    echo -ne "  ${BOLD}🔄 Max battle (0 = infinite) [default 0]: ${NC}"
    read -r INPUT_MAX
    INPUT_MAX=$(echo "$INPUT_MAX" | tr -d '[:space:]')
    [[ "$INPUT_MAX" =~ ^[0-9]+$ ]] || INPUT_MAX=0
    [ "$INPUT_MAX" -eq 0 ] && info "Mode: ∞ infinite" || info "Max: $INPUT_MAX battles"

    # Rounds
    echo ""
    echo -ne "  ${BOLD}🎯 Jumlah round per battle [3/5/7/10, default 5]: ${NC}"
    read -r INPUT_ROUNDS
    INPUT_ROUNDS=$(echo "$INPUT_ROUNDS" | tr -d '[:space:]')
    [[ "$INPUT_ROUNDS" =~ ^(3|5|7|10)$ ]] || INPUT_ROUNDS=5
    info "Rounds: $INPUT_ROUNDS"

    cat > "$ENV_FILE" <<ENVEOF
# MoltArena Auto Battle Bot v4 — Generated $(date '+%Y-%m-%d %H:%M:%S')
# TIDAK perlu auth token!

MOLT_AGENT_ID=${INPUT_AGENT}
MOLT_DELAY_SECONDS=${INPUT_DELAY}
MOLT_MAX_BATTLES=${INPUT_MAX}
MOLT_ROUNDS=${INPUT_ROUNDS}
ENVEOF

    echo ""
    success ".env berhasil dibuat!"
}

show_config() {
    export $(grep -v '^#' "$ENV_FILE" | grep -v '^$' | xargs 2>/dev/null)
    step "Konfigurasi Aktif:"
    divider
    echo -e "  🤖 Agent  : ${CYAN}${MOLT_AGENT_ID}${NC}"
    echo -e "  🎯 Rounds : ${CYAN}${MOLT_ROUNDS:-5}${NC}"
    echo -e "  ⏱  Delay  : ${CYAN}${MOLT_DELAY_SECONDS:-600}s ($(( ${MOLT_DELAY_SECONDS:-600} / 60 )) menit)${NC}"
    [ "${MOLT_MAX_BATTLES:-0}" -eq 0 ] \
        && echo -e "  🔄 Mode   : ${CYAN}∞ Infinite loop${NC}" \
        || echo -e "  🔄 Max    : ${CYAN}${MOLT_MAX_BATTLES} battles${NC}"
    divider
    echo ""
}

edit_env_menu() {
    echo ""
    echo -e "  ${BOLD}📝 File .env sudah ada.${NC}"
    echo ""
    echo -e "  ${CYAN}[1]${NC} Langsung jalankan bot"
    echo -e "  ${CYAN}[2]${NC} Setup ulang config"
    echo -e "  ${CYAN}[3]${NC} Lihat config saat ini"
    echo -e "  ${CYAN}[4]${NC} Keluar"
    echo ""
    echo -ne "  ${BOLD}Pilih [1-4]: ${NC}"
    read -r CHOICE
    case "$CHOICE" in
        1) return ;;
        2) rm -f "$ENV_FILE"; create_env ;;
        3) show_config
           echo -ne "  Lanjut jalankan? [y/N]: "
           read -r CONT
           [[ "$CONT" =~ ^[Yy]$ ]] || exit 0 ;;
        4) exit 0 ;;
        *) info "Melanjutkan dengan config yang ada..." ;;
    esac
}

choose_run_mode() {
    echo -e "${BOLD}  🚀 Cara menjalankan bot:${NC}"
    echo ""
    echo -e "  ${CYAN}[1]${NC} Test 1 battle dulu   — cek koneksi & payload"
    echo -e "  ${CYAN}[2]${NC} Foreground            — log langsung terlihat (Ctrl+C untuk stop)"
    echo -e "  ${CYAN}[3]${NC} Screen (background)   — tetap jalan walau SSH disconnect"
    echo -e "  ${CYAN}[4]${NC} Systemd (service)     — auto-start saat server reboot"
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
    success "Test 1 battle (--once mode)..."
    echo ""
    source "$VENV_DIR/bin/activate"
    "$PYTHON_BIN" "$MAIN_SCRIPT" --once --debug
    echo ""
    echo -ne "  Lanjut loop infinite? [y/N]: "
    read -r CONT
    [[ "$CONT" =~ ^[Yy]$ ]] && run_foreground || exit 0
}

run_foreground() {
    echo ""
    success "Menjalankan bot infinite loop... (Ctrl+C untuk stop)"
    echo ""
    source "$VENV_DIR/bin/activate"
    exec "$PYTHON_BIN" "$MAIN_SCRIPT"
}

run_screen() {
    step "Background dengan screen..."
    command -v screen &>/dev/null || { info "Install screen..."; sudo apt install screen -y; }
    SESSION="molt-bot"
    screen -S "$SESSION" -X quit 2>/dev/null || true
    sleep 1
    screen -dmS "$SESSION" bash -c "
        source '$VENV_DIR/bin/activate'
        '$PYTHON_BIN' '$MAIN_SCRIPT'
    "
    sleep 2
    if screen -list | grep -q "$SESSION"; then
        success "Bot berjalan di background! (session: $SESSION)"
    else
        warn "Screen gagal, coba jalankan foreground"
        return
    fi
    echo ""
    divider
    echo -e "  ${CYAN}screen -r ${SESSION}${NC}              → Lihat log live"
    echo -e "  ${CYAN}Ctrl+A → D${NC}                     → Detach (bot tetap jalan)"
    echo -e "  ${CYAN}screen -S ${SESSION} -X quit${NC}      → Stop bot"
    echo -e "  ${CYAN}tail -f ${LOG_FILE}${NC}   → Log file"
    divider
}

run_systemd() {
    step "Install sebagai systemd service..."
    CURRENT_USER=$(whoami)
    cat > /tmp/molt-battle.service <<SVCEOF
[Unit]
Description=MoltArena Auto Battle Bot v4
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
    [ "$STATUS" = "active" ] && success "Service aktif dan berjalan!" || warn "Status: $STATUS"
    echo ""
    divider
    echo -e "  ${CYAN}sudo systemctl status molt-battle${NC}    → Cek status"
    echo -e "  ${CYAN}sudo journalctl -u molt-battle -f${NC}    → Log live"
    echo -e "  ${CYAN}sudo systemctl restart molt-battle${NC}   → Restart"
    echo -e "  ${CYAN}sudo systemctl stop molt-battle${NC}      → Stop"
    echo -e "  ${CYAN}tail -f ${LOG_FILE}${NC}   → Log file"
    divider
}

# ═══════════════ MAIN ═══════════════
print_banner
check_python
check_script
setup_venv
install_deps

step "Cek file konfigurasi .env..."
if [ ! -f "$ENV_FILE" ]; then
    warn ".env tidak ditemukan → Setup konfigurasi..."
    create_env
else
    success ".env ditemukan"
    edit_env_menu
fi

show_config
choose_run_mode
