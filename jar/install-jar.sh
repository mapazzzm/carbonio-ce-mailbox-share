#!/bin/bash
#
# carbonio-ce-mailbox-share — JAR-часть (бэкенд) / JAR part (backend)
# =================================================================
#
# RU: Снимает жёсткую блокировку делегированного доступа к ящикам со статусом
#     closed («Закрыто/Удалено») и locked («Вход отключён») и показывает их шары
#     в GetShareInfo — чтобы к почте уволенных сотрудников можно было дать доступ
#     по гранту, не открывая ящик. maintenance намеренно остаётся заблокированным.
# EN: Lifts the hard block on delegated access to mailboxes in status closed and
#     locked, and makes their shares visible in GetShareInfo — so you can grant
#     access to a former employee's mail without re-activating the mailbox.
#     maintenance stays blocked on purpose.
#
# Патчатся 3 класса в mailbox.jar / Patches 3 classes in mailbox.jar:
#   * com.zimbra.soap.SoapEngine           — SOAP delegated read
#   * com.zimbra.cs.service.UserServlet     — REST attachment/content read
#   * com.zimbra.cs.account.ShareInfo       — GetShareInfo owner-status filter
# В каждом: разрешаем active OR closed OR locked / allow active OR closed OR locked.
#
# RU: Статусный гейт — только первый барьер: сам ACL-грант на папку проверяется
#     дальше, поэтому делегат без гранта по-прежнему получит PERM_DENIED.
# EN: The status gate is only the first barrier: the folder ACL grant is still
#     enforced, so a delegate without a grant still gets PERM_DENIED.
#
# RU: Метод — декомпиляция ЛОКАЛЬНОГО jar (CFR), патч исходника, рекомпиляция,
#     переупаковка. Исходники Carbonio не распространяются.
# EN: Method — decompile your LOCAL jar (CFR), patch source, recompile, repack.
#     No Carbonio source is redistributed.
#
# RU: Переприменять после `apt upgrade carbonio-appserver`.
# EN: Re-run after `apt upgrade carbonio-appserver`.
#
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
JVM="${CARBONIO_JVM:-/opt/zextras/common/lib/jvm/java}"
JARDIR="${CARBONIO_JARDIR:-/opt/zextras/mailbox/jars}"
CFR_URL="https://repo1.maven.org/maven2/org/benf/cfr/0.152/cfr-0.152.jar"
CFR_SHA256="f686e8f3ded377d7bc87d216a90e9e9512df4156e75b06c655a16648ae8765b2"

say() { echo ">> $1"; }
die() { echo "ERROR / ОШИБКА: $1" >&2; exit 1; }

for t in javac jar java; do
    [ -x "$JVM/bin/$t" ] || die "$JVM/bin/$t not found (set CARBONIO_JVM) / не найден"
done
command -v python3 >/dev/null || die "python3 not installed / не установлен"

LIVE="$JARDIR/mailbox.jar"
[ -f "$LIVE" ] || die "$LIVE not found (set CARBONIO_JARDIR) / не найден"
say "Target jar / Целевой jar: $LIVE"

# Classpath (all Carbonio jars) — empty globs must not abort under set -e.
CP=""
for d in "$JARDIR" /opt/zextras/lib/jars /opt/zextras/common/lib/jars; do
    [ -d "$d" ] || continue
    while IFS= read -r j; do
        case "$j" in *.bak.*) continue;; esac
        CP="$CP$j:"
    done < <(find "$d" -maxdepth 1 -name '*.jar' 2>/dev/null)
done
[ -n "$CP" ] || die "could not build classpath from Carbonio jars / не собран classpath"

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

# 1. CFR decompiler (cached in repo dir, integrity-checked)
CFR="$HERE/cfr-0.152.jar"
if ! { [ -f "$CFR" ] && echo "$CFR_SHA256  $CFR" | sha256sum -c --status; }; then
    say "Downloading CFR 0.152 / Скачиваю CFR 0.152 ..."
    curl -fsSL -o "$CFR" "$CFR_URL"
    echo "$CFR_SHA256  $CFR" | sha256sum -c --status || die "CFR checksum mismatch / контрольная сумма не совпала"
fi

# 2. Decompile the three classes FROM THE LOCAL jar
say "Decompiling / Декомпилирую SoapEngine + UserServlet + ShareInfo ..."
"$JVM/bin/java" -jar "$CFR" "$LIVE" \
    com.zimbra.soap.SoapEngine \
    com.zimbra.cs.service.UserServlet \
    com.zimbra.cs.account.ShareInfo \
    --outputdir "$WORK/src" >/dev/null 2>&1
for f in com/zimbra/soap/SoapEngine.java com/zimbra/cs/service/UserServlet.java com/zimbra/cs/account/ShareInfo.java; do
    [ -f "$WORK/src/$f" ] || die "decompile failed for $f / не удалось декомпилировать"
done

# 3. CFR artifact repair (not our logic): raw Map.Entry in UserServlet does not compile.
sed -i \
  -e 's|^\( *\)Map cookieMap = authToken.cookieMap(false);|\1Map<String, String> cookieMap = authToken.cookieMap(false);|' \
  -e 's|^\( *\)for (Map.Entry ck : cookieMap.entrySet()) {|\1for (Map.Entry<String, String> ck : cookieMap.entrySet()) {|' \
  "$WORK/src/com/zimbra/cs/service/UserServlet.java"

# 4. Apply our patches — SEMANTIC (regex on the logic, not context diffs), so
#    they survive line-number/whitespace/local-variable changes across Carbonio
#    versions, and are idempotent (an already-patched source is detected).
say "Applying patches / Применяю патчи (семантические) ..."
if PATCH_OUT="$(python3 "$HERE/../patches/apply_status_patches.py" "$WORK/src")"; then
    echo "$PATCH_OUT" | sed 's/^STATUS:/  /'
else
    echo "$PATCH_OUT" | sed 's/^STATUS:/  /'
    die "a patch anchor was not found — Carbonio changed the guarded logic; capture the new pattern in patches/apply_status_patches.py / анкор не найден — логика Carbonio изменилась"
fi
# Idempotency: if every class was ALREADY patched, the live jar needs nothing —
# skip the (expensive) recompile/repack. Lets a re-run finish cleanly instead of
# failing, and lets already-installed users re-run harmlessly.
if ! echo "$PATCH_OUT" | grep -q 'STATUS:APPLIED'; then
    say "JAR already patched — nothing to do / jar уже пропатчен — делать нечего"
    exit 0
fi

# 5. Compile the patched classes against the live classpath
say "Compiling / Компилирую ..."
mkdir -p "$WORK/out"
"$JVM/bin/javac" -proc:none -encoding UTF-8 -cp "$CP" -d "$WORK/out" \
    "$WORK/src/com/zimbra/soap/SoapEngine.java" \
    "$WORK/src/com/zimbra/cs/service/UserServlet.java" \
    "$WORK/src/com/zimbra/cs/account/ShareInfo.java" 2>&1 \
    | grep -viE 'deprecat|unchecked|unsafe|Xlint|Recompile with|Note:' || true
for c in com/zimbra/soap/SoapEngine.class com/zimbra/cs/service/UserServlet.class com/zimbra/cs/account/ShareInfo.class; do
    [ -f "$WORK/out/$c" ] || die "compilation failed for $c / компиляция не удалась"
done

# 6. Back up and repackage (all produced .class files, incl. inner classes)
TS="$(date +%Y%m%d_%H%M%S)"
BK="$LIVE.bak.$TS"
cp -p "$LIVE" "$BK"; say "Backup / Бэкап: $BK"
cp "$LIVE" "$WORK/patched.jar"
( cd "$WORK/out" && find . -name '*.class' -printf '%P\0' | xargs -0 "$JVM/bin/jar" uf "$WORK/patched.jar" )

OWNER="$(stat -c '%U:%G' "$LIVE")"
cp "$WORK/patched.jar" "$LIVE"
chown "$OWNER" "$LIVE"; chmod 755 "$LIVE"
say "Patched jar installed / Пропатченный jar установлен (owner $OWNER)."

cat <<'EOF'

RU: Перезапустите mailbox, чтобы загрузить пропатченные классы:
EN: Restart the mailbox to load the patched classes:

    systemctl restart carbonio-appserver.target
    sleep 20
    chown zextras:zextras /opt/zextras/data/tmp/nginx/client
    curl -s http://127.78.0.2:10000/health/live/ -o /dev/null -w "%{http_code}\n"   # 204

RU: Откат / EN: Roll back:  ./uninstall-jar.sh
EOF
