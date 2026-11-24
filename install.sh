#!/usr/bin/env bash
set -Eeuo pipefail

INSTALL_DIR=/opt/roboreka
CONFIG_DIR=/etc/roboreka
SERVICE_NAME=roboreka
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'EOF'
Usage: sudo bash ./install.sh

Install Roboreka from this checkout on an Armbian system, create its
systemd service, and preserve any existing /etc/roboreka/config.toml.
Enable the board's I2C overlay and reboot before running this script.
EOF
    exit 0
fi

[[ $# -eq 0 ]] || fail "Unknown argument: $1 (use --help for usage)"
[[ $EUID -eq 0 ]] || fail "Run this installer as root, for example: sudo bash ./install.sh"
[[ -f /etc/armbian-release ]] || fail "This installer supports Armbian only (/etc/armbian-release not found)"
[[ -f "$SCRIPT_DIR/pyproject.toml" && -f "$SCRIPT_DIR/README.md" \
    && -f "$SCRIPT_DIR/config.example.toml" && -f "$SCRIPT_DIR/deploy/roboreka.service" \
    && -f "$SCRIPT_DIR/deploy/roboreka-web.service" \
    && -d "$SCRIPT_DIR/src/roboreka" ]] \
    || fail "Run this script from a Roboreka source checkout"
command -v systemctl >/dev/null 2>&1 || fail "systemctl is required to install the Roboreka service"
command -v apt-get >/dev/null 2>&1 || fail "apt-get is required to install system dependencies"

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
    fail "Roboreka requires Python 3.9 or newer"
fi

printf 'Installing system dependencies...\n'
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv

if ! getent group roboreka >/dev/null; then
    groupadd --system roboreka
fi
if ! getent group i2c >/dev/null; then
    groupadd --system i2c
fi
if ! id roboreka >/dev/null 2>&1; then
    useradd --system --gid roboreka --groups i2c \
        --home-dir "$INSTALL_DIR" --shell /usr/sbin/nologin roboreka
else
    usermod --append --groups i2c roboreka
fi
if ! id roboreka-web >/dev/null 2>&1; then
    useradd --system --user-group --home-dir /nonexistent \
        --shell /usr/sbin/nologin roboreka-web
fi

printf 'Installing application files in %s...\n' "$INSTALL_DIR"
install -d -o root -g root -m 0755 "$INSTALL_DIR"
cp "$SCRIPT_DIR/pyproject.toml" "$SCRIPT_DIR/README.md" "$INSTALL_DIR/"
cp -a "$SCRIPT_DIR/src" "$INSTALL_DIR/"
chown -R root:root "$INSTALL_DIR"
chmod -R a+rX "$INSTALL_DIR"

install -d -o roboreka -g roboreka -m 0750 "$CONFIG_DIR"
if [[ ! -e "$CONFIG_DIR/config.toml" ]]; then
    install -o root -g roboreka -m 0640 \
        "$SCRIPT_DIR/config.example.toml" "$CONFIG_DIR/config.toml"
else
    chown root:roboreka "$CONFIG_DIR/config.toml"
    chmod 0640 "$CONFIG_DIR/config.toml"
fi

printf 'Creating virtual environment and installing Roboreka...\n'
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/python" -m pip install --editable "$INSTALL_DIR[hardware]"

install -o root -g root -m 0644 \
    "$SCRIPT_DIR/deploy/roboreka.service" "/etc/systemd/system/${SERVICE_NAME}.service"
install -o root -g root -m 0644 \
    "$SCRIPT_DIR/deploy/roboreka-web.service" "/etc/systemd/system/${SERVICE_NAME}-web.service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME" "${SERVICE_NAME}-web"

if [[ -e /dev/i2c-0 ]]; then
    systemctl restart "$SERVICE_NAME"
    systemctl restart "${SERVICE_NAME}-web"
    printf 'Roboreka arm controller and web UI are running.\n'
    printf 'Open http://127.0.0.1:8080 (use SSH port forwarding for remote access).\n'
    printf 'Check logs with: journalctl -u %s -u %s-web -f\n' "$SERVICE_NAME" "$SERVICE_NAME"
else
    systemctl stop "${SERVICE_NAME}-web" >/dev/null 2>&1 || true
    systemctl stop "$SERVICE_NAME" >/dev/null 2>&1 || true
    printf 'Roboreka is installed and enabled, but /dev/i2c-0 is missing.\n' >&2
    printf 'Enable the i2c0 overlay, reboot, then start both apps with: sudo systemctl start %s %s-web\n' "$SERVICE_NAME" "$SERVICE_NAME" >&2
fi
