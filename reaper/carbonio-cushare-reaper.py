#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# carbonio-cushare-reaper — time-limited-access janitor / уборщик срочного доступа
# ================================================================================
#
# RU: Вкладка «Доступ» умеет выдавать доступ к папкам «на срок» — это нативный
#     атрибут `expiry` у folder-гранта Carbonio: по истечении сервер САМ перестаёт
#     пускать делегата (грант исчезает из ACL владельца). Но у права «Отправлять
#     как» (sendAs / zimbraACE) нативного срока НЕТ — оно висит вечно. Этот скрипт
#     снимает такой «осиротевший» sendAs и заодно чистит точку монтирования у
#     делегата, когда соответствующий folder-грант истёк.
#
#     БЕЗ СОСТОЯНИЯ. Единственный источник правды — сам ACL Carbonio:
#       • «у делегата есть mountpoint на владельца, НО активного гранта в ACL
#         владельца больше нет» → доступ истёк → снять sendAs + удалить mountpoint;
#       • «mountpoint нет» → это ручной/легаси sendAs (не через вкладку «Доступ»)
#         → НЕ ТРОГАЕМ (наличие mountpoint — метка того, что связку сделала вкладка).
#     Поэтому давние sendAs и бессрочные шары в безопасности: пока грант в ACL жив
#     (в т.ч. `expiry=0`), sendAs остаётся.
#
# EN: The "Access" tab can grant folder access with an expiry — that is Carbonio's
#     native folder-grant `expiry`: once past, the server itself stops letting the
#     delegate in (the grant vanishes from the owner's ACL). But the "Send As"
#     right (sendAs / zimbraACE) has NO native expiry — it would linger forever.
#     This script revokes such an orphaned sendAs and removes the delegate's
#     mountpoint once the matching folder grant has expired.
#
#     STATELESS. The only source of truth is Carbonio's ACL itself:
#       • "delegate has a mountpoint to the owner, but the owner's ACL no longer
#         has an active grant for them" → access expired → revoke sendAs + drop mp;
#       • "no mountpoint" → a manual/legacy sendAs (not made by the Access tab)
#         → LEAVE IT ALONE (the mountpoint is the marker that the tab made this pair).
#     So old sendAs grants and indefinite shares are safe: while the grant is alive
#     in the ACL (incl. `expiry=0`), the sendAs stays.
#
# RU: Запускается по таймеру (см. .timer) от пользователя zextras. Идемпотентен,
#     ничего не делает, если истёкших связок нет. Ставится вместе со вкладкой
#     «Доступ» (carbonio-ce-mailbox-share). Дополнительного HTTP-сервиса/sidecar
#     НЕ требует — общается с Carbonio через локальные zmprov / zmsoap.
# EN: Runs on a timer (see .timer) as the zextras user. Idempotent; a no-op when
#     nothing expired. Installed alongside the "Access" tab (carbonio-ce-mailbox-
#     share). Needs NO extra HTTP service/sidecar — talks to Carbonio via the local
#     zmprov / zmsoap tools.
#
#   Usage: carbonio-cushare-reaper.py [--dry-run] [--verbose]
#
import os
import re
import sys
import subprocess

ZMPROV = os.environ.get("ZMPROV", "/opt/zextras/bin/zmprov")
ZMSOAP = os.environ.get("ZMSOAP", "/opt/zextras/bin/zmsoap")
CMD_TIMEOUT = 60  # seconds per zmprov/zmsoap call

DRY_RUN = "--dry-run" in sys.argv[1:]
VERBOSE = "--verbose" in sys.argv[1:] or DRY_RUN

# One attribute value on the grantee-account side. zimbraACE format is
# "<grantee-id> <grantee-type> <right>" (a leading "-" means a negative/deny ACE,
# which we ignore — those never come from the Access tab).
_ACE_RE = re.compile(r"^([0-9a-f-]{36})\s+usr\s+sendAs\s*$", re.IGNORECASE)
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
# XML attribute scrapers over zmsoap output (flat, namespace-agnostic).
_GRANT_RE = re.compile(r"<grant\b[^>]*>", re.IGNORECASE)
_LINK_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)


def log(msg):
    print(msg, flush=True)


def vlog(msg):
    if VERBOSE:
        print(msg, flush=True)


def run(argv):
    """Run a command, return (rc, stdout). stderr is dropped (zmprov/zmsoap emit
    log4j init noise there). Never raises."""
    try:
        p = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=CMD_TIMEOUT,
        )
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        log("  ! command failed: %s (%s)" % (" ".join(argv[:2]), exc))
        return 1, ""


def attr(tag, name):
    """Extract attribute `name` from a single XML start-tag string."""
    m = re.search(r'\b%s="([^"]*)"' % re.escape(name), tag)
    return m.group(1) if m else ""


def enumerate_sendas():
    """Return list of (owner_email, grantee_id) for every sendAs ACE on the server.
    One zmprov searchAccounts call; parse '# name' + 'zimbraACE:' lines."""
    rc, out = run([ZMPROV, "sa", "-v", "(zimbraACE=*sendAs)"])
    pairs = []
    owner = None
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("# name "):
            owner = s[len("# name "):].strip()
        elif s.startswith("zimbraACE:") and owner:
            m = _ACE_RE.match(s[len("zimbraACE:"):].strip())
            if m:
                pairs.append((owner, m.group(1).lower()))
    return pairs


def resolve_ids(ids):
    """Map a set of zimbraId -> primary email in one searchAccounts call."""
    ids = [i for i in ids if _UUID_RE.match(i)]
    if not ids:
        return {}
    flt = "(|%s)" % "".join("(zimbraId=%s)" % i for i in ids)
    rc, out = run([ZMPROV, "sa", "-v", flt])
    id2mail = {}
    name = None
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("# name "):
            name = s[len("# name "):].strip()
        elif s.startswith("zimbraId:") and name:
            id2mail[s[len("zimbraId:"):].strip().lower()] = name
    return id2mail


def owner_active_grantees(owner_email):
    """Set of grantee emails+ids that currently hold an ACTIVE grant anywhere in
    the owner's folder tree. Expired grants are already absent from GetFolder."""
    rc, out = run([ZMSOAP, "-z", "-m", owner_email, "-t", "mail",
                   "GetFolderRequest/folder", "@path=/"])
    active = set()
    for g in _GRANT_RE.findall(out):
        d = attr(g, "d").lower()
        zid = attr(g, "zid").lower()
        if d:
            active.add(d)
        if zid:
            active.add(zid)
    return active


def grantee_mountpoints(grantee_email):
    """Map owner_email(lower) -> [mountpoint folder ids] in the grantee's mailbox."""
    rc, out = run([ZMSOAP, "-z", "-m", grantee_email, "-t", "mail",
                   "GetFolderRequest"])
    mp = {}
    for lnk in _LINK_RE.findall(out):
        owner = attr(lnk, "owner").lower()
        fid = attr(lnk, "id")
        if owner and fid:
            mp.setdefault(owner, []).append(fid)
    return mp


def revoke_sendas(owner_email, grantee_email):
    rc, out = run([ZMPROV, "rvr", "account", owner_email, "usr",
                   grantee_email, "sendAs"])
    return rc == 0 or "already" in out.lower() or out.strip() == ""


def delete_mountpoint(grantee_email, folder_id):
    rc, out = run([ZMSOAP, "-z", "-m", grantee_email, "-t", "mail",
                   "FolderActionRequest/action", "@op=delete", "@id=%s" % folder_id])
    return "FolderActionResponse" in out


def main():
    pairs = enumerate_sendas()
    if not pairs:
        vlog("no sendAs grants on the server — nothing to do")
        return 0
    vlog("sendAs grants found: %d" % len(pairs))

    id2mail = resolve_ids({gid for _, gid in pairs})

    # Cache per-owner active grantees and per-grantee mountpoints (batched).
    owner_cache = {}
    grantee_mp_cache = {}
    expired = 0

    for owner_email, grantee_id in pairs:
        grantee_email = id2mail.get(grantee_id)
        if not grantee_email:
            vlog("  ? grantee id %s unresolved (deleted account?) — skip" % grantee_id)
            continue

        if grantee_email not in grantee_mp_cache:
            grantee_mp_cache[grantee_email] = grantee_mountpoints(grantee_email)
        mp = grantee_mp_cache[grantee_email].get(owner_email.lower(), [])
        if not mp:
            # No mountpoint to this owner → not an Access-tab share (manual/legacy
            # sendAs). Leave it alone.
            vlog("  · %s -> %s: no mountpoint (manual sendAs) — leave" % (owner_email, grantee_email))
            continue

        if owner_email not in owner_cache:
            owner_cache[owner_email] = owner_active_grantees(owner_email)
        active = owner_cache[owner_email]
        if grantee_email.lower() in active or grantee_id in active:
            vlog("  · %s -> %s: grant still active — leave" % (owner_email, grantee_email))
            continue

        # Mountpoint exists but the owner has no active grant → access expired.
        expired += 1
        log("EXPIRED: %s -> %s (revoke sendAs, drop %d mountpoint(s))%s"
            % (owner_email, grantee_email, len(mp), "  [dry-run]" if DRY_RUN else ""))
        if DRY_RUN:
            continue
        if revoke_sendas(owner_email, grantee_email):
            log("  sendAs revoked")
        else:
            log("  ! sendAs revoke may have failed")
        for fid in mp:
            if delete_mountpoint(grantee_email, fid):
                log("  mountpoint %s removed" % fid)
            else:
                log("  ! mountpoint %s removal failed" % fid)

    if expired == 0:
        vlog("no expired sendAs grants — nothing revoked")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # never crash the timer / не роняем таймер
        log("cushare-reaper fatal: %s" % exc)
        sys.exit(0)
