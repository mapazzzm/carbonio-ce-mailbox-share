#!/bin/bash
#
# carbonio-ce-mailbox-share — full uninstaller / полный откат
# RU: Откатывает обе части из бэкапов. EN: Rolls both parts back from backups.
#
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

echo ">> [1/2] Admin UI tab / вкладка админки"
python3 "$HERE/admin-ui/install.py" uninstall

echo; echo ">> [2/2] JAR patch (backend) / JAR-патч (бэкенд)"
bash "$HERE/jar/uninstall-jar.sh"

cat <<'EOF'

RU: Откат готов. Перезапустите mailbox и обновите страницу админки.
EN: Rolled back. Restart the mailbox and reload the admin UI.

    systemctl restart carbonio-appserver.target
    sleep 20
    chown zextras:zextras /opt/zextras/data/tmp/nginx/client
EOF
