# carbonio-ce-mailbox-share

[<sup>ru</sup> Русский](#русский) | [<sup>en</sup> English](#english)

Управление общим доступом к почтовым ящикам прямо в **carbonio-admin-ui**: вкладка «Доступ» в свойствах
ящика (права `rwixd`, «отправка от имени», поиск по email/ФИО, авто-подключение, **доступ «на срок»**) **плюс**
серверный патч, который позволяет давать доступ к почте ящиков в статусе **«Закрыто»** и **«Заблокировано»** —
не открывая их (сценарий уволенного сотрудника).

Manage mailbox sharing right inside **carbonio-admin-ui**: an "Access" tab in the mailbox properties
(`rwixd` rights, "send as", e-mail/name search, auto-mountpoint, **time-limited access**) **plus** a backend
patch that lets you grant access to mail of **closed** and **locked** mailboxes without re-activating them
(the "former employee" case).

Протестировано на / Tested on **Carbonio CE 26.3, 26.6 и сборке с `carbonio-admin-ui` 0.15.2** (`carbonio-admin-ui` 0.12.x / 0.13.x / 0.15.x, `mailbox.jar` from `carbonio-appserver`, Ubuntu 22.04/24.04, JDK 21).

---

## Русский

### Что это даёт

- В **свойствах ящика** (Управление → домен → ящик) появляется вкладка **«Доступ»** с двумя разделами:
  - **«Ящики, добавленные в этот»** — чужие ящики, к которым у этого пользователя есть доступ (появляются
    в его веб-интерфейсе). Кнопки **Добавить / Изменить / Убрать**.
  - **«Кому выдан доступ к этому ящику»** — обратный список, тоже с **Добавить / Изменить / Отозвать**.
- В каждой форме: отдельные галочки прав **`r w i x d`** (чтение / запись / вставка / удаление / действия),
  переключатель **«отправка от имени» (Send As)**, поиск-подсказки по **email и свойствам** (ФИО, `displayName`,
  `sn`, `givenName`, `uid`), авто-создание **mountpoint** (ящик появляется у пользователя сам).
- **Доступ к закрытым/заблокированным ящикам.** «Отправка от имени» для них автоматически недоступна
  (от закрытого ящика слать нельзя).
- **Доступ «на срок».** В форме — галочка **«Бессрочный доступ»** (по умолчанию включена); сняв её, можно
  выбрать **дату**, до которой доступ действует. По истечении Carbonio **сам** перестаёт пускать делегата
  (нативный `expiry` у folder-гранта), а фоновый уборщик снимает «отправку от имени» и убирает подключённый
  ящик. Уже выданные доступы считаются бессрочными и в любой момент правятся через **«Изменить»** (можно менять
  и права, и срок). Сценарий: замещающему на 25 дней отпуска — доступ к ящику ушедшего, дальше сам исчезает.
- Интерфейс двуязычный: русский при русской локали Carbonio, английский при любой другой.

### Проблема, которую решает бэкенд-патч

Carbonio (наследие Zimbra) жёстко запрещает **делегированный** доступ к ящику, если его статус не `active`,
и **прячет его шары** из `GetShareInfo`. Поэтому нельзя дать новому сотруднику почту уволенного, не переведя
ящик обратно в `active` (а это снова логин и приём почты). Патч снимает это ограничение для статусов
**`closed`** и **`locked`**, оставляя **`maintenance`** заблокированным (доступ к ящику во время
бэкапа/миграции опасен).

### Что патчится

**Бэкенд — 3 класса в `mailbox.jar`** (пакет `jar/`):

| Класс | Что делает стоково | Патч |
|---|---|---|
| `com.zimbra.soap.SoapEngine` | делегированный SOAP к не-`active` ящику → `ACCOUNT_INACTIVE` | пускает `active` OR `closed` OR `locked` |
| `com.zimbra.cs.service.UserServlet` | то же для REST (вложения/содержимое в вебе) | то же |
| `com.zimbra.cs.account.ShareInfo` | `GetShareInfo` пропускает шары не-`active` владельцев | отдаёт шары `active`/`closed`/`locked` |

> **Безопасность.** Статусный гейт — только первый барьер: **ACL-грант на папку проверяется дальше**, поэтому
> делегат без явного гранта всё равно получит `PERM_DENIED`. `GetShareInfo` отдаёт только те шары, что **реально
> выданы запрашивающему**. `maintenance` остаётся заблокированным. Патч ничего не ослабляет сверх того, что
> администратор сам разрешил грантом.

**Фронтенд — вкладка в `carbonio-admin-ui`** (пакет `admin-ui/`): инъекция React-компонента в `shell.mjs`
+ строки в `i18n/ru.json`. Всё поверх штатных админ-SOAP (`FolderAction grant`, `GrantRight/RevokeRight sendAs`,
`CreateMountpoint`, `GetShareInfo`, `SearchDirectory`).

### Как работает JAR-патч

Ваш **локально установленный** `mailbox.jar` декомпилируется (CFR), к исходнику применяется маленький
патч (`patches/*.status.patch`), затронутые классы перекомпилируются и кладутся обратно в jar. **Исходники
Carbonio не распространяются** — декомпилируется ваш собственный jar.

### Как истекает доступ «на срок»

Срок хранится в **нативном** атрибуте `expiry` folder-гранта Carbonio: доступ к папкам снимает **сам сервер**
точно в срок — без нашего кода. Но у права «отправка от имени» (`sendAs`) нативного срока нет, поэтому проект
ставит крошечный **systemd-таймер** `carbonio-cushare-reaper.timer` (`reaper/`, каждые 30 мин, от пользователя
`zextras`). Уборщик **без состояния** — единственный источник правды — сам ACL. Он снимает `sendAs` и удаляет
подключённый ящик только когда у делегата **есть** точка монтирования на владельца, но активного гранта в ACL
владельца **уже нет** (= доступ истёк). Нет точки монтирования → это ручной/давний `sendAs`, он **не трогается**;
бессрочные шары (`expiry=0`) не трогаются никогда. Общается с Carbonio через локальные `zmprov`/`zmsoap` —
отдельный HTTP-сервис или sidecar **не нужен** (проект самодостаточен).

### Установка

Одной строкой — склонирует, поставит обе части и перезапустит mailbox:

```bash
git clone https://github.com/mapazzzm/carbonio-ce-mailbox-share && cd carbonio-ce-mailbox-share && sudo ./install.sh
```

После этого обновите страницу админки (`Ctrl+F5`) — появится вкладка «Доступ». Рестарт mailbox
`install.sh` делает сам и ждёт `health 204`; пропустить его можно `NO_RESTART=1 sudo ./install.sh`.

Части можно ставить по отдельности:

```bash
sudo bash jar/install-jar.sh          # только бэкенд
python3 admin-ui/install.py install   # только вкладка админки
python3 admin-ui/install.py check     # диагностика: применён ли UI-патч, найдены ли анкоры
sudo bash reaper/install-reaper.sh    # только уборщик sendAs (systemd-таймер)
```

### Откат

```bash
sudo ./uninstall.sh            # обе части из бэкапов, затем рестарт mailbox
```

### После обновлений

- `apt upgrade carbonio-appserver` перезаписывает `mailbox.jar` → повторите `jar/install-jar.sh` + рестарт.
- `apt upgrade carbonio-admin-ui` перезаписывает `shell.mjs`/`ru.json` → повторите `admin-ui/install.py install`.
- Уборщик `sendAs` **не слетает** при `apt upgrade` (свои файлы вне пакетов Carbonio). После `git pull`
  достаточно `sudo bash reaper/install-reaper.sh` (идемпотентно). **Обновление с прошлой версии проекта:**
  `git pull && sudo ./install.sh` — вкладка обновляется на месте (`install.py` умеет замену), уборщик
  доустанавливается. Ранее выданные доступы остаются бессрочными.

> ⚠️ **Про UI-часть.** React-компонент завязан на **минифицированные имена конкретной сборки**
> `carbonio-admin-ui`. Поддерживаются три варианта, `install.py` выбирает нужный сам: v1 — 0.12.x
> (`component.js`), v2 — 0.13.x (`component_v2.js`), v3 — 0.15.x (`component_v3.js`). Если `install.py`
> пишет, что анкор не найден, — ваша сборка новее; добавьте вариант: снимите анкоры (`A_COMP`/`A_TAB`/`A_BR`
> в `admin-ui/install.py`) и минифицированные псевдонимы (контекст аккаунта, `useTranslation`, snackbar, SOAP-обёртка,
> поиск, Button, Checkbox, React/jsx) под свой `shell.mjs`. JAR-часть версионно-устойчива (патч исходника), это ограничение касается только UI.

### Требования

`javac`, `jar`, `java` (JDK 21 из состава Carbonio: `/opt/zextras/common/lib/jvm/java`), `patch`, `python3`,
опционально `node` (для проверки синтаксиса UI-патча). CFR 0.152 скачивается автоматически (проверяется по SHA-256).

---

## English

### What you get

- The **mailbox properties** (Manage → domain → account) gain an **"Access"** tab with two sections:
  - **"Mailboxes added to this one"** — other mailboxes this user can access (they appear in the user's web
    interface). **Add / Edit / Remove**.
  - **"Who has access to this mailbox"** — the reverse list, also **Add / Edit / Revoke**.
- Each form has per-right checkboxes **`r w i x d`** (read / write / insert / delete / actions), a **Send As**
  toggle, type-ahead search by **e-mail and directory attributes** (display name, `sn`, `givenName`, `uid`),
  and automatic **mountpoint** creation (the mailbox shows up for the grantee by itself).
- **Access to closed/locked mailboxes.** "Send As" is disabled for them automatically (you cannot send from a
  closed mailbox).
- **Time-limited access.** The form has an **"Indefinite access"** checkbox (on by default); clear it to pick a
  **date** through which the access is valid. When it passes, Carbonio itself stops letting the delegate in (the
  native folder-grant `expiry`), and a background janitor revokes "Send As" and removes the mounted mailbox.
  Existing grants count as indefinite and can be changed anytime via **Edit** (both rights and the deadline).
  Use case: give a stand-in 25 days of access to a colleague on vacation; it then disappears on its own.
- Bilingual UI: Russian on a Russian Carbonio locale, English otherwise.

### The problem the backend patch solves

Carbonio (Zimbra heritage) hard-blocks **delegated** access to any non-`active` mailbox and **hides its shares**
from `GetShareInfo`. So you cannot give a new employee the mail of a former one without switching the mailbox
back to `active` (which re-enables login and mail delivery). The patch lifts this for **`closed`** and
**`locked`**, keeping **`maintenance`** blocked (accessing a mailbox during backup/migration is unsafe).

### What is patched

**Backend — 3 classes in `mailbox.jar`** (`jar/`):

| Class | Stock behaviour | Patch |
|---|---|---|
| `com.zimbra.soap.SoapEngine` | delegated SOAP to a non-`active` mailbox → `ACCOUNT_INACTIVE` | allow `active` OR `closed` OR `locked` |
| `com.zimbra.cs.service.UserServlet` | same for REST (attachments/content in the web UI) | same |
| `com.zimbra.cs.account.ShareInfo` | `GetShareInfo` skips shares of non-`active` owners | return shares of `active`/`closed`/`locked` |

> **Security.** The status gate is only the first barrier: **the folder ACL grant is still enforced**, so a
> delegate without an explicit grant still gets `PERM_DENIED`. `GetShareInfo` only returns shares **actually
> granted to the requester**. `maintenance` stays blocked. The patch relaxes nothing beyond what an admin
> already allowed with a grant.

**Frontend — an admin tab in `carbonio-admin-ui`** (`admin-ui/`): injects a React component into `shell.mjs`
plus strings into `i18n/ru.json`. Everything runs over the stock admin SOAP (`FolderAction grant`,
`GrantRight/RevokeRight sendAs`, `CreateMountpoint`, `GetShareInfo`, `SearchDirectory`).

### How the JAR patch works

Your **locally installed** `mailbox.jar` is decompiled (CFR), a small source patch (`patches/*.status.patch`)
is applied, the touched classes are recompiled and put back into the jar. **No Carbonio source is
redistributed** — your own jar is decompiled on your machine.

### How time-limited access expires

The deadline lives in Carbonio's **native** folder-grant `expiry` attribute: folder access is removed by the
**server itself**, exactly on time, with no code of ours. The "Send As" right (`sendAs`) has no native expiry,
so the project installs a tiny **systemd timer** `carbonio-cushare-reaper.timer` (`reaper/`, every 30 min, as
the `zextras` user). The janitor is **stateless** — the only source of truth is the ACL itself. It revokes
`sendAs` and removes the mounted mailbox only when the delegate **has** a mountpoint to the owner but the
owner's ACL **no longer** holds an active grant for them (= access expired). No mountpoint → a manual/legacy
`sendAs`, **left alone**; indefinite shares (`expiry=0`) are never touched. It talks to Carbonio via the local
`zmprov`/`zmsoap` — **no** separate HTTP service or sidecar is needed (the project is self-contained).

### Install

One line — clones, installs both parts and restarts the mailbox:

```bash
git clone https://github.com/mapazzzm/carbonio-ce-mailbox-share && cd carbonio-ce-mailbox-share && sudo ./install.sh
```

Then hard-reload the admin UI (`Ctrl+F5`) — the "Access" tab appears. `install.sh` restarts the mailbox and
waits for `health 204` by itself; skip it with `NO_RESTART=1 sudo ./install.sh`.

Parts can be installed separately:

```bash
sudo bash jar/install-jar.sh          # backend only
python3 admin-ui/install.py install   # admin tab only
python3 admin-ui/install.py check     # diagnostics: is the UI patch applied, are anchors present
sudo bash reaper/install-reaper.sh    # sendAs janitor only (systemd timer)
```

### Uninstall

```bash
sudo ./uninstall.sh            # both parts from backups, then restart the mailbox
```

### After upgrades

- `apt upgrade carbonio-appserver` overwrites `mailbox.jar` → re-run `jar/install-jar.sh` + restart.
- `apt upgrade carbonio-admin-ui` overwrites `shell.mjs`/`ru.json` → re-run `admin-ui/install.py install`.
- The `sendAs` janitor is **not** affected by `apt upgrade` (its files live outside Carbonio packages). After a
  `git pull`, refresh it with `sudo bash reaper/install-reaper.sh` (idempotent). **Upgrading from an earlier
  version of this project:** `git pull && sudo ./install.sh` — the tab updates in place (`install.py` supports
  replacement) and the janitor is installed. Previously granted access stays indefinite.

> ⚠️ **About the UI part.** The React component depends on the **minified identifiers of a specific
> `carbonio-admin-ui` build**. Three variants are supported and auto-detected by `install.py`: v1 — 0.12.x
> (`component.js`), v2 — 0.13.x (`component_v2.js`), v3 — 0.15.x (`component_v3.js`). If `install.py` reports a
> missing anchor, your build is newer — add a variant: capture the anchors (`A_COMP`/`A_TAB`/`A_BR` in
> `admin-ui/install.py`) and the minified aliases (account context, `useTranslation`, snackbar, SOAP wrapper,
> directory search, Button, Checkbox, React/jsx) from your `shell.mjs`. The JAR part is version-robust (source patch); this caveat is UI-only.

### Requirements

`javac`, `jar`, `java` (JDK 21 shipped with Carbonio: `/opt/zextras/common/lib/jvm/java`), `patch`, `python3`,
optionally `node` (to syntax-check the UI patch). CFR 0.152 is downloaded automatically (verified by SHA-256).

---

## License

GNU AGPL v3.0 — same as Carbonio CE itself, since these patches modify Carbonio code. See [LICENSE](LICENSE).
