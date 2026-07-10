#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
carbonio-ce-mailbox-share — semantic JAR-source patcher
=======================================================
RU: Накладывает 3 правки на ДЕКОМПИЛИРОВАННЫЙ (CFR) исходник mailbox.jar,
    разрешая делегированный доступ к ящикам active OR closed OR locked
    (maintenance остаётся заблокированным). Вместо контекстных .patch-диффов —
    СЕМАНТИЧЕСКИЕ regex-замены: устойчивы к номерам строк, пробелам и
    переименованию локальных переменных между версиями Carbonio. Идемпотентно:
    уже пропатченный файл распознаётся и пропускается.
EN: Applies 3 edits to the DECOMPILED (CFR) mailbox.jar source, allowing
    delegated access to active OR closed OR locked mailboxes (maintenance stays
    blocked). Semantic regex rewrites instead of context .patch diffs — robust
    to line numbers, whitespace and local-variable renames across Carbonio
    versions. Idempotent: an already-patched file is detected and skipped.

Usage: apply_status_patches.py <decompiled-src-dir>
Exit: 0 = every file applied or already-patched; 3 = some anchor not found
      (Carbonio changed the logic — capture new pattern); 2 = bad args/IO.
Prints one "STATUS:<APPLIED|ALREADY|NOTFOUND> <file>" line per class.
"""
import sys, os, re

# (relative path, anchor regex, replacement, already-patched marker regex)
# Each anchor captures the local variable names so renames don't break it.
PATCHES = [
    # SoapEngine: boolean bl2 = inactive = !target.getAccountStatus(prov).equals("active");
    # already-marker is broad on purpose: it recognises ANY variant that lets
    # "closed" through (this semantic patch, or the earlier context-diff one that
    # used a temp var) so re-runs on an old install skip cleanly. Vanilla
    # SoapEngine never compares the status to "closed", so no false positive.
    ("com/zimbra/soap/SoapEngine.java",
     re.compile(r'(=\s*)!\s*(\w+)\.getAccountStatus\((\w+)\)\.equals\("active"\)'),
     lambda m: '%s!(%s.getAccountStatus(%s).equals("active")||%s.getAccountStatus(%s).equals("closed")||%s.getAccountStatus(%s).equals("locked"))'
               % (m.group(1), m.group(2), m.group(3), m.group(2), m.group(3), m.group(2), m.group(3)),
     re.compile(r'\.equals\("closed"\)')),

    # UserServlet: if (!("active".equals(acctStatus) || context.authToken ...))
    ("com/zimbra/cs/service/UserServlet.java",
     re.compile(r'"active"\.equals\((\w+)\)\s*\|\|\s*(\w+)\.authToken'),
     lambda m: '"active".equals(%s) || "closed".equals(%s) || "locked".equals(%s) || %s.authToken'
               % (m.group(1), m.group(1), m.group(1), m.group(2)),
     re.compile(r'"closed"\.equals\(')),

    # ShareInfo: (status = account.getAccountStatus()) != null && !status.isActive()
    ("com/zimbra/cs/account/ShareInfo.java",
     re.compile(r'\((\w+)\s*=\s*(\w+)\.getAccountStatus\(\)\)\s*!=\s*null\s*&&\s*!\s*\1\.isActive\(\)'),
     lambda m: '(%s = %s.getAccountStatus()) != null && !(%s.isActive() || %s.isClosed() || %s.isLocked())'
               % (m.group(1), m.group(2), m.group(1), m.group(1), m.group(1)),
     re.compile(r'\.isClosed\(\)')),
]


def main():
    if len(sys.argv) != 2:
        print("usage: apply_status_patches.py <src-dir>", file=sys.stderr); sys.exit(2)
    src = sys.argv[1]
    overall = 0
    for rel, anchor, repl, marker in PATCHES:
        path = os.path.join(src, rel)
        try:
            with open(path, encoding="utf-8") as fh:
                c = fh.read()
        except OSError as e:
            print("STATUS:NOTFOUND %s (%s)" % (rel, e)); overall = 3; continue
        if marker.search(c):
            print("STATUS:ALREADY %s" % rel); continue
        n = len(anchor.findall(c))
        if n == 0:
            print("STATUS:NOTFOUND %s" % rel); overall = 3; continue
        if n > 1:
            # Ambiguous anchor — refuse rather than patch the wrong site.
            print("STATUS:NOTFOUND %s (anchor matched %d times)" % (rel, n)); overall = 3; continue
        c = anchor.sub(repl, c, count=1)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(c)
        print("STATUS:APPLIED %s" % rel)
    sys.exit(overall)


if __name__ == "__main__":
    main()
