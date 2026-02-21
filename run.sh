#!/bin/bash
# MoltArena Auto Battle Bot v5 — Setup & Run
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
    clear
    echo ""
    echo -e "${CYAN}${BOLD}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}${BOLD}║      🥊  MoltArena Auto Battle Bot v5  🥊               ║${NC}"
    echo -e "${CYAN}${BOLD}║   1v1 Roast | Random | English | Loop 10 Menit         ║${NC}"
    echo -e "${CYAN}${BOLD}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

check_python() {
    step "Cek Python..."
    if command -v python3 &>/dev/null; then
        success "$(python3 --version)"
        PYTHON_BIN="python3"
    else
        error "Python3 tidak ada! Install: sudo apt install python3 python3-pip python3-venv -y"
        exit 1
    fi
}

setup_venv() {
    step "Setup Virtual Environment..."
    [ ! -d "$VENV_DIR" ] && $PYTHON_BIN -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    PYTHON_BIN="$VENV_DIR/bin/python"
    PIP_BIN="$VENV_DIR/bin/pip"
    success "venv siap"
}

install_deps() {
    step "Install Dependencies..."
    $PIP_BIN install -q --upgrade pip
    [ -f "$REQUIREMENTS" ] && $PIP_BIN install -q -r "$REQUIREMENTS" || $PIP_BIN install -q requests python-dotenv
    success "requests & python-dotenv siap"
}

create_env() {
    echo ""
    echo -e "${YELLOW}${BOLD}  📝 Setup Konfigurasi${NC}"
    echo ""

    # ── Pilih metode auth ─────────────────────────────────────
    echo -e "  ${BOLD}🔑 Pilih metode autentikasi:${NC}"
    echo ""
    echo -e "  ${CYAN}[1]${NC} API Key ${GREEN}(DISARANKAN)${NC} — dari settings/api, tidak expired"
    echo -e "  ${CYAN}[2]${NC} Refresh Token ${GREEN}(auto-refresh tiap 55 menit)${NC}"
    echo -e "  ${CYAN}[3]${NC} Cookie — dari browser Application tab (expire 1 jam)"
    echo ""
    echo -ne "  ${BOLD}Pilih [1/2]: ${NC}"
    read -r AUTH_CHOICE

    INPUT_APIKEY=""
    INPUT_COOKIE=""

    if [ "$AUTH_CHOICE" = "1" ]; then
        echo ""
        echo -e "  ${DIM}Buka: https://moltarena.crosstoken.io/settings/api${NC}"
        echo -e "  ${DIM}Klik Generate/Create API Key → Copy key (pk_live_...)${NC}"
        echo ""
        while true; do
            echo -ne "  ${BOLD}Paste API Key (pk_live_...): ${NC}"
            read -r INPUT_APIKEY
            INPUT_APIKEY=$(echo "$INPUT_APIKEY" | tr -d '[:space:]')
            if [[ "$INPUT_APIKEY" == pk_live_* ]]; then
                success "API Key valid"
                break
            else
                warn "Harus dimulai 'pk_live_'. Coba lagi."
            fi
        done
    else
        echo ""
        echo -e "  ${BOLD}Cara ambil Cookie:${NC}"
        echo -e "  ${DIM}1. Buka moltarena.crosstoken.io (sudah login)${NC}"
        echo -e "  ${DIM}2. F12 → tab Application${NC}"
        echo -e "  ${DIM}3. Kiri: Storage → Cookies → moltarena.crosstoken.io${NC}"
        echo -e "  ${DIM}4. Cari cookie sb-* → copy Name dan Value${NC}"
        echo -e "  ${DIM}5. Format: name1=value1; name2=value2${NC}"
        echo ""
        echo -ne "  ${BOLD}Paste Cookie string: ${NC}"
        read -r INPUT_COOKIE
        [ -n "$INPUT_COOKIE" ] && success "Cookie diterima" || warn "Cookie kosong"
    fi

    # ── Agent ID ──────────────────────────────────────────────
    echo ""
    echo -e "  ${DIM}Agent ID ada di URL: moltarena.crosstoken.io/agents/AGENT-ID${NC}"
    while true; do
        echo -ne "  ${BOLD}🤖 Agent ID: ${NC}"
        read -r INPUT_AGENT
        INPUT_AGENT=$(echo "$INPUT_AGENT" | tr -d '[:space:]')
        [ -n "$INPUT_AGENT" ] && { success "Agent: $INPUT_AGENT"; break; } || warn "Tidak boleh kosong."
    done

    # ── Delay ─────────────────────────────────────────────────
    echo ""
    echo -ne "  ${BOLD}⏱  Delay detik [default 600 = 10 menit]: ${NC}"
    read -r INPUT_DELAY
    INPUT_DELAY=$(echo "$INPUT_DELAY" | tr -d '[:space:]')
    [[ "$INPUT_DELAY" =~ ^[0-9]+$ ]] || INPUT_DELAY=600

    # ── Max ───────────────────────────────────────────────────
    echo -ne "  ${BOLD}🔄 Max battle [0 = infinite]: ${NC}"
    read -r INPUT_MAX
    INPUT_MAX=$(echo "$INPUT_MAX" | tr -d '[:space:]')
    [[ "$INPUT_MAX" =~ ^[0-9]+$ ]] || INPUT_MAX=0

    # ── Tulis .env ────────────────────────────────────────────
    cat > "$ENV_FILE" <<ENVEOF
# MoltArena Auto Battle Bot v5 — $(date '+%Y-%m-%d %H:%M:%S')

MOLT_API_KEY=${INPUT_APIKEY}
MOLT_COOKIE=${INPUT_COOKIE}
MOLT_AGENT_ID=${INPUT_AGENT}
MOLT_DELAY_SECONDS=${INPUT_DELAY}
MOLT_MAX_BATTLES=${INPUT_MAX}
MOLT_ROUNDS=5
ENVEOF
    echo ""
    success ".env berhasil dibuat!"
}

show_config() {
    set -a; source "$ENV_FILE" 2>/dev/null; set +a
    step "Konfigurasi Aktif:"
    divider
    if [ -n "$MOLT_API_KEY" ]; then
        echo -e "  🔑 Auth   : ${GREEN}API Key (${MOLT_API_KEY:0:12}...${MOLT_API_KEY: -4})${NC}"
    elif [ -n "$MOLT_COOKIE" ]; then
        echo -e "  🔑 Auth   : ${GREEN}Cookie (${#MOLT_COOKIE} chars)${NC}"
    else
        echo -e "  🔑 Auth   : ${RED}BELUM DISET!${NC}"
    fi
    echo -e "  🤖 Agent  : ${CYAN}${MOLT_AGENT_ID}${NC}"
    echo -e "  ⏱  Delay  : ${CYAN}${MOLT_DELAY_SECONDS:-600}s ($(( ${MOLT_DELAY_SECONDS:-600} / 60 )) menit)${NC}"
    [ "${MOLT_MAX_BATTLES:-0}" -eq 0 ] \
        && echo -e "  🔄 Mode   : ${CYAN}∞ Infinite${NC}" \
        || echo -e "  🔄 Max    : ${CYAN}${MOLT_MAX_BATTLES} battles${NC}"
    divider
    echo ""
}

edit_env_menu() {
    echo ""
    echo -e "  ${BOLD}📝 File .env sudah ada.${NC}"
    echo ""
    echo -e "  ${CYAN}[1]${NC} Langsung jalankan"
    echo -e "  ${CYAN}[2]${NC} Setup ulang config"
    echo -e "  ${CYAN}[3]${NC} Ganti API Key / Cookie saja"
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
            echo -ne "  ${BOLD}API Key baru (pk_live_...) atau Cookie baru: ${NC}"
            read -r NEW_AUTH
            NEW_AUTH=$(echo "$NEW_AUTH" | tr -d '[:space:]' 2>/dev/null || echo "$NEW_AUTH")
            if [[ "$NEW_AUTH" == pk_live_* ]]; then
                sed -i "s|^MOLT_API_KEY=.*|MOLT_API_KEY=${NEW_AUTH}|" "$ENV_FILE"
                sed -i "s|^MOLT_COOKIE=.*|MOLT_COOKIE=|" "$ENV_FILE"
                success "API Key diperbarui!"
            elif [ -n "$NEW_AUTH" ]; then
                sed -i "s|^MOLT_COOKIE=.*|MOLT_COOKIE=${NEW_AUTH}|" "$ENV_FILE"
                sed -i "s|^MOLT_API_KEY=.*|MOLT_API_KEY=|" "$ENV_FILE"
                success "Cookie diperbarui!"
            fi
            ;;
        4) show_config; echo -ne "  Lanjut? [y/N]: "; read -r X; [[ "$X" =~ ^[Yy]$ ]] || exit 0 ;;
        5) exit 0 ;;
    esac
}

choose_run_mode() {
    echo -e "${BOLD}  🚀 Cara menjalankan:${NC}"
    echo ""
    echo -e "  ${CYAN}[1]${NC} Test 1 battle dulu  ${DIM}(cek koneksi & auth)${NC}"
    echo -e "  ${CYAN}[2]${NC} Foreground           ${DIM}(log langsung, Ctrl+C untuk stop)${NC}"
    echo -e "  ${CYAN}[3]${NC} Screen background    ${DIM}(tetap jalan walau SSH disconnect)${NC}"
    echo -e "  ${CYAN}[4]${NC} Systemd service      ${DIM}(auto-start saat reboot)${NC}"
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
    success "Test 1 battle..."
    source "$VENV_DIR/bin/activate"
    "$PYTHON_BIN" "$MAIN_SCRIPT" --once --debug
    echo ""
    echo -ne "  ${BOLD}Lanjut loop infinite? [y/N]: ${NC}"
    read -r C
    [[ "$C" =~ ^[Yy]$ ]] && run_foreground || exit 0
}

run_foreground() {
    echo ""
    success "Menjalankan loop infinite... (Ctrl+C untuk stop)"
    source "$VENV_DIR/bin/activate"
    exec "$PYTHON_BIN" "$MAIN_SCRIPT"
}

run_screen() {
    step "Screen background..."
    command -v screen &>/dev/null || sudo apt install screen -y
    SESSION="molt-bot"
    screen -S "$SESSION" -X quit 2>/dev/null || true
    sleep 1
    screen -dmS "$SESSION" bash -c "source '$VENV_DIR/bin/activate'; '$PYTHON_BIN' '$MAIN_SCRIPT'"
    sleep 2
    screen -list | grep -q "$SESSION" && success "Berjalan di screen '$SESSION'" || warn "Screen gagal"
    echo ""; divider
    echo -e "  ${CYAN}screen -r $SESSION${NC}              → Lihat log"
    echo -e "  ${CYAN}Ctrl+A → D${NC}                    → Detach"
    echo -e "  ${CYAN}screen -S $SESSION -X quit${NC}      → Stop"
    echo -e "  ${CYAN}tail -f $LOG_FILE${NC}"
    divider
}

run_systemd() {
    step "Systemd service..."
    CURRENT_USER=$(whoami)
    cat > /tmp/molt-battle.service <<SVCEOF
[Unit]
Description=MoltArena Auto Battle Bot v5
After=network-online.target

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
    echo ""; divider
    echo -e "  ${CYAN}sudo systemctl status molt-battle${NC}"
    echo -e "  ${CYAN}sudo journalctl -u molt-battle -f${NC}"
    echo -e "  ${CYAN}sudo systemctl restart molt-battle${NC}"
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
    warn ".env tidak ditemukan → setup config..."
    create_env
else
    success ".env ditemukan"
    edit_env_menu
fi

show_config
choose_run_mode
