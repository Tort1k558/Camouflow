---
title: Hosted catalog tasks
order: 80
---

# Hosted catalog tasks

Hosted tasks run on CamouFlow's private servers while your desktop is closed.
They are optional: your existing local profiles and scenarios continue running
locally. The public desktop repository does not contain hosted backend or worker
source code.

## Create a monitor

1. Open **Tasks → Hosted tasks**, then sign in to the web console and select
   your workspace. The desktop opens your configured server; it never puts
   desktop credentials in the browser URL. Web sign-in is independent.
2. A workspace manager creates a task and imports UTF-8 CSV, for example:

   ```csv
   url,sku
   https://camouflow.site/assets/catalog-demo.html,demo
   ```

3. Set the URL column to `url` and define result selectors:

   ```text
   price=.price
   stock=.stock
   ```

   The demo is an owned test fixture, not a real product offer. Each selector
   must match exactly one element. Target domains require administrator approval.
4. Choose **Static HTML** or **JavaScript browser**. Static mode cannot sign in
   or read JavaScript-rendered content. Browser contexts are ephemeral: no login
   state survives a row. Arbitrary uploaded scripts are not supported.
5. Choose manual runs, an interval of at least 15 minutes, or a daily time with
   an IANA timezone. Optional approval expires after 24 hours. Missed scheduled
   occurrences coalesce into one run rather than replaying a backlog.

## Results and manual intervention

Operators can start, approve and cancel runs. View rows to see each input,
result, status and attempt. Changes compare previous results for the same URL
and selectors. Export CSV uses authenticated requests and protects against
spreadsheet formulas.

A browser row can pause for login, CAPTCHA or review. Open its live screenshot,
click a field, send text or keyboard input, and continue once the expected fields
are ready. Password fields are masked. Entered text is not saved in task results
or audit payloads. Only the run initiator or a workspace manager can intervene.
The separate 30–900 second intervention window does not extend when refreshed.
This is manual assistance, not automatic CAPTCHA solving.

Failures and worker interruptions are never automatically replayed. Select
only failed/interrupted rows and request a retry; successful rows are not repeated.
Cancelling a run also closes its active browser context.

## Completion webhooks

A manager can configure an administrator-approved HTTPS receiver. Save the
one-response signing key securely. Verify `X-CamouFlow-Signature` using HMAC-SHA256
over `timestamp.delivery-id.raw-body`, reject stale timestamps and deduplicate
`X-CamouFlow-Delivery`. Up to five delivery attempts are made.

Events include run status, row-status counts and changed row numbers; they do
not include row inputs, extracted results or entered secrets. Use your receiver
to forward notifications to tools such as n8n or Telegram. No receiver is
configured automatically, and delivery is at-least-once, not exactly-once.

## Current safety limits

One hosted browser slot; up to 500 rows and 20 input columns per task, a 2 MB
dataset, ten result selectors and 30–900 seconds for intervention. Workspaces
have bounded task, queue and result storage. Browser and webhook destinations
are administrator-approved; this is not unrestricted remote code execution.

## Кратко по-русски

Откройте **Tasks → Hosted tasks**, войдите в веб-консоль и выберите команду.
Менеджер создаёт монитор из CSV, задаёт столбец URL, CSS-селекторы результатов
и расписание. Локальные сценарии продолжают работать как раньше.

**Static HTML** читает готовый HTML; **JavaScript browser** запускает временный
браузер. Для входа, CAPTCHA или проверки откройте строки запуска, используйте
снимок экрана и нажмите **Continue task**. Это ручное вмешательство, не обход
CAPTCHA. После строки браузерная сессия уничтожается.

Неудачные строки повторяются только по явному запросу; успешные не запускаются
снова. Webhook требует разрешённый HTTPS-получатель: проверяйте подпись,
время события и идентификатор доставки. Получатель уведомлений автоматически
не создаётся, серверные исходники остаются приватными.
