#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# carbonio-ce-mailbox-share — admin UI installer / инсталлятор админ-UI
# ====================================================================
#
# RU: Встраивает в свойства ящика (carbonio-admin-ui) вкладку «Доступ» с двумя
#     разделами — «какие ящики добавлены в этот» и «кому выдан доступ к этому» —
#     с Add/Edit/Remove, правами rwixd, sendAs, поиском по email/ФИО и авто-mountpoint.
# EN: Adds an "Access" tab to the mailbox properties (carbonio-admin-ui) with two
#     sections — "mailboxes added to this one" and "who has access to this one" —
#     with Add/Edit/Remove, rwixd rights, sendAs, e-mail/name search and auto-mountpoint.
#
# RU: ВНИМАНИЕ: JS-компонент завязан на минифицированные имена конкретной сборки
#     carbonio-admin-ui. Если анкоры не найдены — версия отличается, адаптируйте их
#     под свой shell.mjs. JAR-часть (jar/) версионно-устойчива, это относится только к UI.
# EN: NOTE: the JS component depends on the minified identifiers of a specific
#     carbonio-admin-ui build. If an anchor is not found, your build differs — adapt
#     the anchors to your shell.mjs. The JAR part (jar/) is version-robust; this caveat
#     is UI-only.
#
# RU: Переприменять после `apt upgrade carbonio-admin-ui`.
# EN: Re-run after `apt upgrade carbonio-admin-ui`.
#
#   python3 install.py [install|check|uninstall]
#
import sys, os, json, time, shutil, collections

HERE = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.environ.get("CARBONIO_ADMIN_UI", "/opt/zextras/admin/iris/carbonio-admin-ui")
SHELL = os.path.join(UI_DIR, "shell.mjs")
RUJSON = os.path.join(UI_DIR, "i18n", "ru.json")
MARKER = "__cuShareIntoView"

# Anchors (build-specific) / Анкоры (зависят от сборки)
A_COMP = "},EFe=()=>{const n=ai(J2)"
A_TAB  = 'be&&ge.push({id:"delegates",label:P("label.delegates","DELEGATES").toLocaleUpperCase(),CustomComponent:et});'
A_BR   = "q===ike&&t.jsx(EFe,{})"

TAB_ADD = 'ge.push({id:"cuShareInto",label:P("cushare.into_tab","Access").toLocaleUpperCase(),CustomComponent:et});'
BR_ADD  = ',q==="cuShareInto"&&t.jsx(__cuShareIntoView,{})'

def log(msg): print(">> " + msg)
def die(msg): print("ERROR / ОШИБКА: " + msg, file=sys.stderr); sys.exit(1)

def backup(path):
    bk = "%s.bak_cushare_%s" % (path, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(path, bk); log("Backup / Бэкап: " + bk)

def chown_zextras(path):
    try:
        import pwd, grp
        os.chown(path, pwd.getpwnam("zextras").pw_uid, grp.getgrnam("zextras").gr_gid)
    except Exception:
        pass  # not fatal when testing off-box / не критично вне сервера

def do_check():
    s = open(SHELL, encoding="utf-8").read()
    installed = MARKER in s
    print("shell.mjs: %s" % ("INSTALLED / УСТАНОВЛЕН" if installed else "not installed / не установлен"))
    for name, a in (("component", A_COMP), ("tab", A_TAB), ("branch", A_BR)):
        n = s.count(a)
        tag = "ok" if n == 1 else ("N/A after install" if installed else "MISSING / НЕ НАЙДЕН")
        print("  anchor %-9s x%d  %s" % (name, n, tag))
    try:
        d = json.load(open(RUJSON, encoding="utf-8"))
        print("ru.json cushare: %s" % ("present / есть" if "cushare" in d else "missing / нет"))
    except Exception as e:
        print("ru.json: %s" % e)
    return installed

def apply_shell():
    s = open(SHELL, encoding="utf-8").read()
    if MARKER in s:
        log("shell.mjs already patched / уже пропатчен — skip"); return
    comp = open(os.path.join(HERE, "component.js"), encoding="utf-8").read().strip()
    for name, a in (("component", A_COMP), ("tab", A_TAB), ("branch", A_BR)):
        if s.count(a) != 1:
            die("anchor '%s' found %d times (expected 1) — build differs, adapt anchors / версия отличается"
                % (name, s.count(a)))
    s = s.replace(A_COMP, "}," + comp + ",EFe=()=>{const n=ai(J2)", 1)
    s = s.replace(A_TAB, A_TAB + TAB_ADD, 1)
    s = s.replace(A_BR, A_BR + BR_ADD, 1)
    # syntax sanity if node is available / проверка синтаксиса, если есть node
    # tmp must end in .mjs so node --check parses it as an ES module / иначе node трактует как CommonJS
    tmp = SHELL + ".cushare_tmp.mjs"
    open(tmp, "w", encoding="utf-8").write(s)
    if shutil.which("node"):
        if os.system("node --check '%s' >/dev/null 2>&1" % tmp) != 0:
            os.remove(tmp); die("patched shell.mjs failed node --check / синтаксис не прошёл")
    backup(SHELL)
    os.replace(tmp, SHELL); chown_zextras(SHELL)
    log("shell.mjs patched / пропатчен")

def merge_rujson():
    add = json.load(open(os.path.join(HERE, "ru.strings.json"), encoding="utf-8"))
    d = json.load(open(RUJSON, encoding="utf-8"), object_pairs_hook=collections.OrderedDict)
    if d.get("cushare") == add.get("cushare"):
        log("ru.json already has cushare / уже содержит cushare — skip"); return
    backup(RUJSON)
    d["cushare"] = add["cushare"]
    json.dump(d, open(RUJSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    chown_zextras(RUJSON)
    log("ru.json merged / обновлён")

def do_uninstall():
    # restore newest backups / восстановить свежайшие бэкапы
    import glob
    for path in (SHELL, RUJSON):
        bks = sorted(glob.glob(path + ".bak_cushare_*"))
        if bks:
            shutil.copy2(bks[-1], path); chown_zextras(path)
            log("restored / восстановлен %s <- %s" % (path, os.path.basename(bks[-1])))
        else:
            log("no backup for / нет бэкапа для %s (leave as is)" % path)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "install"
    for p in (SHELL, RUJSON):
        if not os.path.exists(p): die("%s not found (set CARBONIO_ADMIN_UI) / не найден" % p)
    if mode == "check":
        do_check()
    elif mode == "uninstall":
        do_uninstall()
        print("\nRU: обновите страницу админки. EN: reload the admin UI.")
    elif mode == "install":
        apply_shell(); merge_rujson()
        print("\nRU: Готово. Обновите страницу админки (Ctrl+F5).")
        print("EN: Done. Hard-reload the admin UI (Ctrl+F5).")
    else:
        die("usage: install.py [install|check|uninstall]")

if __name__ == "__main__":
    main()
