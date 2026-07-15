#!/bin/bash
#
# install-reaper.sh — install/refresh the time-limited-access sendAs janitor.
# ===========================================================================
# RU: Ставит скрипт-уборщик sendAs (истечение доступа «на срок») + systemd-таймер.
#     Идемпотентно — можно запускать повторно (после git pull) для обновления.
#     Требует root (пишет в /usr/local/bin и /etc/systemd/system). Ставится
#     вместе с проектом; НЕ слетает при `apt upgrade carbonio-*` (свои файлы).
# EN: Installs the sendAs janitor (time-limited access expiry) + a systemd timer.
#     Idempotent — safe to re-run (after git pull) to update. Needs root (writes
#     to /usr/local/bin and /etc/systemd/system). Installed with the project; it
#     does NOT get clobbered by `apt upgrade carbonio-*` (own files).
#
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

BIN=/usr/local/bin/carbonio-cushare-reaper.py
UNIT_DIR=/etc/systemd/system

if [ "$(id -u)" != "0" ]; then
    echo "ERROR / ОШИБКА: run as root / запустите от root" >&2
    exit 1
fi

echo ">> installing reaper script -> $BIN"
install -m 0755 "$HERE/carbonio-cushare-reaper.py" "$BIN"

echo ">> installing systemd units -> $UNIT_DIR"
install -m 0644 "$HERE/carbonio-cushare-reaper.service" "$UNIT_DIR/carbonio-cushare-reaper.service"
install -m 0644 "$HERE/carbonio-cushare-reaper.timer"   "$UNIT_DIR/carbonio-cushare-reaper.timer"

echo ">> enabling timer / включаю таймер"
systemctl daemon-reload
systemctl enable --now carbonio-cushare-reaper.timer

echo ">> self-test (dry-run) / самопроверка (без изменений):"
# Runs the very same code the timer will, but read-only, as zextras.
sudo -u zextras HOME=/opt/zextras PATH=/opt/zextras/bin:/opt/zextras/common/bin:/usr/bin:/bin \
    /usr/bin/python3 "$BIN" --dry-run 2>/dev/null | tail -n 3 || true

cat <<'EOF'

RU: Готово. Таймер carbonio-cushare-reaper.timer запускает уборщик каждые 30 мин.
    Логи:   journalctl -u carbonio-cushare-reaper.service
    Ручной прогон (без изменений): sudo -u zextras /usr/local/bin/carbonio-cushare-reaper.py --dry-run
EN: Done. The carbonio-cushare-reaper.timer runs the janitor every 30 min.
    Logs:   journalctl -u carbonio-cushare-reaper.service
    Manual dry-run: sudo -u zextras /usr/local/bin/carbonio-cushare-reaper.py --dry-run
EOF
