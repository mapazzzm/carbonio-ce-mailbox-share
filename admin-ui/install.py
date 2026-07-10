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
# RU: ДВЕ ВЕРСИИ СБОРКИ. JS-компонент завязан на минифицированные имена конкретной
#     сборки carbonio-admin-ui, а они меняются между версиями:
#       v1 — admin-console-ui 0.12.x (CE 26.3): component.js, анкоры EFe/ai(J2)/ike.
#       v2 — admin-console-ui 0.13.x (CE 26.6, Vite): component_v2.js, анкоры K/v/Nde.
#     Инсталлятор сам определяет версию по содержимому shell.mjs. Если ни один набор
#     анкоров не подошёл — сборка снова изменилась, снимите новые имена и добавьте v3.
#     JAR-часть (jar/) версионно-устойчива — это касается только UI.
# EN: TWO BUILD VARIANTS. The JS component depends on the minified identifiers of a
#     specific carbonio-admin-ui build, which change across versions:
#       v1 — admin-console-ui 0.12.x (CE 26.3): component.js, anchors EFe/ai(J2)/ike.
#       v2 — admin-console-ui 0.13.x (CE 26.6, Vite): component_v2.js, anchors K/v/Nde.
#     The installer auto-detects the variant from shell.mjs. If neither anchor set
#     matches, the build changed again — capture the new identifiers and add v3.
#     The JAR part (jar/) is version-robust; this caveat is UI-only.
#
# RU: Работает на Ubuntu 22.04 и 24.04 (нужен только python3 и, желательно, node
#     для проверки синтаксиса). Переприменять после `apt upgrade carbonio-admin-ui`.
# EN: Works on Ubuntu 22.04 and 24.04 (needs only python3, plus node for the optional
#     syntax check). Re-run after `apt upgrade carbonio-admin-ui`.
#
#   python3 install.py [install|check|uninstall]
#
import sys, os, json, time, shutil, collections

HERE = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.environ.get("CARBONIO_ADMIN_UI", "/opt/zextras/admin/iris/carbonio-admin-ui")
SHELL = os.path.join(UI_DIR, "shell.mjs")
# i18n dir differs across builds: 0.12.x had ./i18n/ru.json inside the UI dir;
# 0.13.x symlinks ./i18n -> /opt/zextras/admin/iris/i18n. Both resolve via UI_DIR.
RUJSON = os.path.join(UI_DIR, "i18n", "ru.json")
MARKER = "__cuShareIntoView"

# Locale files to enrich with the `cushare` namespace: <strings file in repo> ->
# <locale json name under i18n/>. English is covered by the component's inline
# defaults, so no en.json merge is needed. Carbonio serves ONE pt.json for all
# Portuguese incl. Brazilian (regional pt-BR browsers fall back to pt.json), so
# a single pt.json entry covers Brazilian too. A locale is skipped if either the
# repo strings file or the target i18n json is absent on this install.
LOCALES = {
    "ru.strings.json": "ru.json",
    "pt.strings.json": "pt.json",
}

# Build variants / Варианты сборки.
# Each: anchors (must each occur exactly once), component file, tab/branch snippets.
VARIANTS = {
    "v1": {  # admin-console-ui 0.12.x (CE 26.3)
        "component": "component.js",
        "A_COMP": "},EFe=()=>{const n=ai(J2)",
        "A_TAB":  'be&&ge.push({id:"delegates",label:P("label.delegates","DELEGATES").toLocaleUpperCase(),CustomComponent:et});',
        "A_BR":   "q===ike&&t.jsx(EFe,{})",
        # component is spliced into the same comma-let chain, right before EFe
        "COMP_REPL": lambda comp, A: "}," + comp + ",EFe=()=>{const n=ai(J2)",
        "TAB_ADD": 'ge.push({id:"cuShareInto",label:P("cushare.into_tab","Access").toLocaleUpperCase(),CustomComponent:et});',
        "BR_ADD":  ',q==="cuShareInto"&&t.jsx(__cuShareIntoView,{})',
    },
    "v2": {  # admin-console-ui 0.13.x (CE 26.6, Vite)
        "component": "component_v2.js",
        # inject the component into the `let G=...,K=[...]` chain, right before K
        "A_COMP": "K=[{id:`general`,label:m(`label.general`,`GENERAL`),CustomComponent:G}",
        "A_TAB":  "A&&K.push({id:`delegates`,label:m(`label.delegates`,`DELEGATES`).toLocaleUpperCase(),CustomComponent:G});",
        "A_BR":   "v===`delegates`&&(0,Z.jsx)(Nde,{})",
        "COMP_REPL": lambda comp, A: comp + "," + A,
        "TAB_ADD": "K.push({id:`cuShareInto`,label:m(`cushare.into_tab`,`Access`).toLocaleUpperCase(),CustomComponent:G});",
        "BR_ADD":  ",v===`cuShareInto`&&(0,Z.jsx)(__cuShareIntoView,{})",
    },
}

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

def detect_variant(s):
    """Return (name, cfg) of the build whose anchors are all present exactly once."""
    for name, cfg in VARIANTS.items():
        if all(s.count(cfg[a]) == 1 for a in ("A_COMP", "A_TAB", "A_BR")):
            return name, cfg
    return None, None

def do_check():
    s = open(SHELL, encoding="utf-8").read()
    installed = MARKER in s
    name, cfg = detect_variant(s)
    print("shell.mjs: %s" % ("INSTALLED / УСТАНОВЛЕН" if installed else "not installed / не установлен"))
    print("build variant / вариант сборки: %s" % (name or "UNKNOWN / НЕИЗВЕСТЕН"))
    if cfg:
        for aname, key in (("component", "A_COMP"), ("tab", "A_TAB"), ("branch", "A_BR")):
            n = s.count(cfg[key])
            tag = "ok" if n == 1 else ("N/A after install" if installed else "MISSING / НЕ НАЙДЕН")
            print("  anchor %-9s x%d  %s" % (aname, n, tag))
    else:
        print("  анкоры ни одной версии не найдены — сборка изменилась, добавьте v3")
    for strings_file, locale_name in LOCALES.items():
        path = os.path.join(UI_DIR, "i18n", locale_name)
        if not os.path.exists(path):
            print("  %s: отсутствует на этой сборке / not present — skip" % locale_name)
            continue
        try:
            d = json.load(open(path, encoding="utf-8"))
            print("  %s cushare: %s" % (locale_name, "present / есть" if "cushare" in d else "missing / нет"))
        except Exception as e:
            print("  %s: %s" % (locale_name, e))
    return installed

def apply_shell():
    s = open(SHELL, encoding="utf-8").read()
    if MARKER in s:
        log("shell.mjs already patched / уже пропатчен — skip"); return
    name, cfg = detect_variant(s)
    if not cfg:
        die("no known build anchors matched — carbonio-admin-ui build changed, "
            "capture new identifiers and add a variant / сборка изменилась")
    log("detected build / определена сборка: " + name)
    comp = open(os.path.join(HERE, cfg["component"]), encoding="utf-8").read().strip()
    s = s.replace(cfg["A_COMP"], cfg["COMP_REPL"](comp, cfg["A_COMP"]), 1)
    s = s.replace(cfg["A_TAB"], cfg["A_TAB"] + cfg["TAB_ADD"], 1)
    s = s.replace(cfg["A_BR"], cfg["A_BR"] + cfg["BR_ADD"], 1)
    # syntax sanity if node is available / проверка синтаксиса, если есть node
    # tmp must end in .mjs so node --check parses it as an ES module / иначе CommonJS
    tmp = SHELL + ".cushare_tmp.mjs"
    open(tmp, "w", encoding="utf-8").write(s)
    if shutil.which("node"):
        if os.system("node --check '%s' >/dev/null 2>&1" % tmp) != 0:
            os.remove(tmp); die("patched shell.mjs failed node --check / синтаксис не прошёл")
    else:
        log("node not found — skipping syntax check / node нет, пропускаю проверку синтаксиса")
    backup(SHELL)
    os.replace(tmp, SHELL); chown_zextras(SHELL)
    log("shell.mjs patched (%s) / пропатчен" % name)

def merge_locales():
    for strings_file, locale_name in LOCALES.items():
        src = os.path.join(HERE, strings_file)
        path = os.path.join(UI_DIR, "i18n", locale_name)
        if not os.path.exists(src):
            log("%s отсутствует в репо / missing in repo — skip" % strings_file); continue
        if not os.path.exists(path):
            log("%s отсутствует на сборке / not present on this build — skip" % locale_name); continue
        add = json.load(open(src, encoding="utf-8"))
        d = json.load(open(path, encoding="utf-8"), object_pairs_hook=collections.OrderedDict)
        if d.get("cushare") == add.get("cushare"):
            log("%s already has cushare / уже содержит — skip" % locale_name); continue
        backup(path)
        d["cushare"] = add["cushare"]
        json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        chown_zextras(path)
        log("%s merged / обновлён" % locale_name)

def do_uninstall():
    # restore newest backups / восстановить свежайшие бэкапы
    import glob
    targets = [SHELL] + [os.path.join(UI_DIR, "i18n", ln) for ln in LOCALES.values()]
    for path in targets:
        bks = sorted(glob.glob(path + ".bak_cushare_*"))
        if bks:
            shutil.copy2(bks[-1], path); chown_zextras(path)
            log("restored / восстановлен %s <- %s" % (path, os.path.basename(bks[-1])))
        else:
            log("no backup for / нет бэкапа для %s (leave as is)" % path)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "install"
    if not os.path.exists(SHELL):
        die("%s not found (set CARBONIO_ADMIN_UI) / не найден" % SHELL)
    if mode == "check":
        do_check()
    elif mode == "uninstall":
        do_uninstall()
        print("\nRU: обновите страницу админки. EN: reload the admin UI.")
    elif mode == "install":
        apply_shell(); merge_locales()
        print("\nRU: Готово. Обновите страницу админки (Ctrl+F5).")
        print("EN: Done. Hard-reload the admin UI (Ctrl+F5).")
    else:
        die("usage: install.py [install|check|uninstall]")

if __name__ == "__main__":
    main()
