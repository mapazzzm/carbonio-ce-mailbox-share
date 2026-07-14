#!/bin/bash
#
# carbonio-ce-mailbox-share — full installer / полный инсталлятор
# ==============================================================
# RU: Ставит три части — JAR-патч (бэкенд), вкладку «Доступ» в админке (UI) и
#     уборщик sendAs для доступа «на срок» (systemd-таймер).
# EN: Installs three parts — the JAR patch (backend), the "Access" admin UI tab,
#     and the sendAs janitor for time-limited access (a systemd timer).
#
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "=============================================================="
echo " carbonio-ce-mailbox-share — install / установка"
echo "=============================================================="

echo; echo ">> [1/3] JAR patch (backend) / JAR-патч (бэкенд)"
bash "$HERE/jar/install-jar.sh"

echo; echo ">> [2/3] Admin UI tab / вкладка админки"
python3 "$HERE/admin-ui/install.py" install

echo; echo ">> [3/3] Time-limited-access sendAs janitor / уборщик срочного доступа (sendAs)"
bash "$HERE/reaper/install-reaper.sh"

# RU: Рестарт mailbox для загрузки пропатченных классов (пропустить: NO_RESTART=1).
# EN: Restart the mailbox to load the patched classes (skip with NO_RESTART=1).
if [ "${NO_RESTART:-0}" != "1" ]; then
    echo; echo ">> Restarting mailbox / Перезапускаю mailbox (carbonio-appserver) ..."
    systemctl restart carbonio-appserver.target
    sleep 20
    chown zextras:zextras /opt/zextras/data/tmp/nginx/client 2>/dev/null || true
    code=""
    for _ in $(seq 1 40); do
        code="$(curl -s http://127.78.0.2:10000/health/live/ -o /dev/null -w '%{http_code}' 2>/dev/null || true)"
        [ "$code" = "204" ] && break
        sleep 3
    done
    echo ">> mailbox health: $code (204 = OK)"
else
    echo; echo ">> NO_RESTART=1 — restart skipped / рестарт пропущен."
    echo "   systemctl restart carbonio-appserver.target && sleep 20 && chown zextras:zextras /opt/zextras/data/tmp/nginx/client"
fi

cat <<'EOF'

==============================================================
RU: Готово. Обновите страницу админки (Ctrl+F5) — появится вкладка «Доступ».
EN: Done. Hard-reload the admin UI (Ctrl+F5) — the "Access" tab will appear.
==============================================================
EOF
