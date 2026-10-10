---
title: Team center
order: 81
---

# Team center

The Team center connects human assignments to actual browser execution. It is
an optional private-server feature, not a sprint planner or a replacement for
your local scenario queue. Availability requires backend revision
`0012_team_center`; older servers do not support this page.

## Assign work

1. Open **Tasks → Team center**, sign in independently to the web console,
   and select the workspace.
2. A manager creates an assignment with a title, description, assignee,
   priority and optional deadline. Deadlines use the creator's local timezone
   in the form and are stored as timezone-aware instants.
3. Choose an existing hosted task, or a local scenario and optional profile.
   All resources and the assignee must belong to that workspace. Viewers cannot
   be assigned execution work. Resource references cannot change after runs
   have been linked: create another assignment for a different workflow.
4. The assignee or a manager starts the hosted task, or runs the local scenario
   in desktop and links the matching server-recorded run afterwards. Assignment
   creation does not enable schedules or start work automatically.

An assignment and a run are separate records. Multiple runs can be attached;
failed runs do not complete the assignment. Scheduled hosted runs and explicit
retries can be linked to the same assignment through **Link run**.

## Review results

Assignments move through **Ready → In progress → On review → Completed**.
The assignee submits work for review; only a manager can mark it completed,
cancel it or reopen it. The latest linked run must have succeeded, and no linked
run may still be active when submitting or completing work. Review does not
independently verify third-party data: the manager must inspect the results.

Open **View results** to inspect the run. Comments support discussion, but are
visible to workspace members: never paste passwords, cookies or tokens.
Concurrent edits are rejected with a conflict; refresh before saving again.

## Help queue

**Needs help** lists unexpired browser rows awaiting human action. It shows the
task, row, reason, original deadline and teammate currently handling it.

- The run initiator, assignment's current assignee or a manager may help.
- **Take ownership** creates a two-minute claim; an open Team center renews it.
- Other teammates cannot control or view that claimed browser row until the
  claim expires or is released. Managers can explicitly release a claim.
- Reassignment or access revocation invalidates a claim when its holder no
  longer has permission to help; the next authorized teammate need not wait
  for the claim timeout.
- Claim renewal never extends the worker's original intervention deadline.
- **Continue task** resumes execution through the existing authenticated
  browser controls. Browser state remains ephemeral.

Closing the page lets the claim expire. Help ownership is coordination, not a
grant of access to another workspace or to arbitrary profiles.

## Existing roles remain

| Role | Team center permissions |
| --- | --- |
| Viewer | Read assignments, discussion, run results and help queue |
| Operator | Execute assigned work, link matching runs, submit review, comment; intervene in own or assigned runs |
| Manager | Create/edit/assign work, review/cancel/reopen assignments, manage help claims |
| Admin | Manager permissions plus invitations and management of lower-ranked members |
| Owner | Admin permissions plus team settings and ownership transfer |

**Settings → Transfer ownership** promotes an existing active teammate to owner
and changes the caller to admin in one transaction. Existing additional owners
are retained. Admins cannot invite or promote peers/owners, or reset passwords
of higher-ranked members. The last owner cannot be removed or demoted.

Assignments do not introduce profile-level ACLs or change existing team-wide
profile, scenario, export or pool permissions. Existing invitations and access
revocation remain in **Members / Invites**. Hosted execution stays restricted
to approved domains and the available server capacity.

Limits: 500 assignments per workspace, 100 linked runs and 200 comments per
assignment; comments are at most 2,000 characters. Lists are paginated. Filters
currently apply to the displayed page.

## Кратко по-русски

**Командный центр** связывает поручение, ответственного и реальные запуски.
Менеджер назначает работу, исполнитель запускает hosted-задачу либо локальный
сценарий и передаёт успешный результат на проверку. Менеджер завершает поручение.
Очередь «Нужна помощь» позволяет одному участнику взять браузер в работу,
не продлевая исходный срок ручного вмешательства. Спринты и отдельная система
ролей не добавляются; серверный код остаётся приватным.
