#!/bin/bash
#
# carbonio-ce-mailbox-share — откат JAR-части / roll back the JAR part.
# RU: Восстанавливает mailbox.jar из самого свежего бэкапа mailbox.jar.bak.*,
#     созданного install-jar.sh. Требует рестарт appserver.
# EN: Restores mailbox.jar from the newest mailbox.jar.bak.* created by install-jar.sh.
#     Requires an appserver restart.
#
set -euo pipefail

JARDIR="${CARBONIO_JARDIR:-/opt/zextras/mailbox/jars}"
LIVE="$JARDIR/mailbox.jar"

BK="$(ls -1t "$LIVE".bak.* 2>/dev/null | head -1 || true)"
[ -n "$BK" ] || { echo "ERROR / ОШИБКА: no $LIVE.bak.* backup found / бэкап не найден" >&2; exit 1; }

OWNER="$(stat -c '%U:%G' "$LIVE")"
echo ">> Restoring from / Восстанавливаю из: $BK"
cp -p "$BK" "$LIVE"
chown "$OWNER" "$LIVE"; chmod 755 "$LIVE"
echo ">> Original mailbox.jar restored / Восстановлен оригинал (owner $OWNER)."
cat <<'EOF'

RU: Перезапустите mailbox, чтобы вернуть штатное поведение:
EN: Restart the mailbox to restore stock behaviour:

    systemctl restart carbonio-appserver.target
    sleep 20
    chown zextras:zextras /opt/zextras/data/tmp/nginx/client
EOF
