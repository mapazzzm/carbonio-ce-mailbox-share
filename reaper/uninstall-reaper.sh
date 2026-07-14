#!/bin/bash
#
# uninstall-reaper.sh — remove the time-limited-access sendAs janitor.
# RU: Останавливает и удаляет таймер/сервис/скрипт уборщика. Уже выданные
#     folder-гранты со сроком продолжат истекать нативно (это делает сам Carbonio);
#     без уборщика только sendAs перестанет сниматься автоматически.
# EN: Stops and removes the janitor timer/service/script. Existing time-limited
#     folder grants keep expiring natively (Carbonio itself); without the janitor
#     only the sendAs part will no longer be auto-revoked.
#
set -euo pipefail
if [ "$(id -u)" != "0" ]; then echo "run as root / запустите от root" >&2; exit 1; fi

systemctl disable --now carbonio-cushare-reaper.timer 2>/dev/null || true
systemctl stop carbonio-cushare-reaper.service 2>/dev/null || true
rm -f /etc/systemd/system/carbonio-cushare-reaper.timer \
      /etc/systemd/system/carbonio-cushare-reaper.service \
      /usr/local/bin/carbonio-cushare-reaper.py
systemctl daemon-reload
echo ">> reaper removed / уборщик удалён"
