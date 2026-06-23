#!/usr/bin/env bash
# Instala arranque automático de la mini pantalla al iniciar sesión (systemd user).
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_NAME="turing-smart-screen.service"
USER_UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
DESKTOP_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"

chmod +x "$DIR/scripts/wait-usb-screen.sh" "$DIR/scripts/start-at-boot.sh" "$DIR/scripts/start-screen.sh" \
  "$DIR/scripts/poll-fps.sh" "$DIR/scripts/install-fan-modules.sh"

mkdir -p "$USER_UNIT_DIR" "$DESKTOP_DIR"

# Sustituir %h por $HOME en la plantilla
sed "s|%h|$HOME|g" "$DIR/scripts/turing-smart-screen.user.service" >"$USER_UNIT_DIR/$UNIT_NAME"
sed "s|%h|$HOME|g" "$DIR/scripts/turing-fps.user.service" >"$USER_UNIT_DIR/turing-fps.service"

# Fallback .desktop por si graphical-session tarda
cat >"$DESKTOP_DIR/turing-smart-screen.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Turing Smart Screen
Comment=Monitor USB de sistema en mini pantalla
Exec=$DIR/scripts/start-screen.sh
Hidden=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=8
EOF

systemctl --user daemon-reload
systemctl --user enable "$UNIT_NAME" turing-fps.service

# Detener instancias manuales previas
pkill -f "$DIR/.venv/bin/python3 main.py" 2>/dev/null || true
rm -f /tmp/turing-smart-screen.lock /tmp/turing-smart-screen.pid
sleep 2

systemctl --user restart turing-fps.service "$UNIT_NAME" || true

echo ""
echo "✓ Servicio usuario: $UNIT_NAME"
echo "✓ Servicio FPS: turing-fps.service"
echo "✓ Autostart desktop: $DESKTOP_DIR/turing-smart-screen.desktop"
echo ""
if ! ls /sys/class/hwmon/hwmon*/fan*_input >/dev/null 2>&1; then
  echo "⚠️  Ventiladores CPU: ejecuta una vez (requiere contraseña):"
  echo "   cd $DIR && sudo ./scripts/install-fan-modules.sh"
  echo "   (o reinicia el PC tras ese comando)"
fi
echo ""
echo "Comandos útiles:"
echo "  systemctl --user status turing-smart-screen"
echo "  journalctl --user -u turing-smart-screen -f"
echo "  tail -f /tmp/turing-screen.log"
echo ""
if [ "$(loginctl show-user "$(whoami)" -p Linger --value 2>/dev/null)" != "yes" ]; then
  echo "ℹ️  Linger=no: la pantalla arranca al iniciar sesión gráfica (login)."
  echo "   Si usas autologin, el .desktop en autostart también la levanta tras 8s."
fi
echo ""
systemctl --user status "$UNIT_NAME" --no-pager || true