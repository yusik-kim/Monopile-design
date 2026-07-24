# CLAUDE.md

Ask clarification if needed 

## TBD backlog maintenance

This repo tracks a running agenda backlog at `docs/TBD.md` (a table: Date
Added / Item / Status / Status Updated). Items are added via `/TBD <item>`.

Status values: `open` / `discussed` (no implementation needed) / `implemented`
/ `obsoleted` / `archived`.

**Proactively keep `docs/TBD.md` current without waiting to be asked.**
Whenever, during a session, a backlog item is clearly resolved — you
implement something that matches an open item, a conversation thoroughly
discusses an item and concludes no implementation is needed, or a later
decision makes an item moot — update that row's `Status` and
`Status Updated` columns yourself (today's date), and mention the update in
one short line. This is the primary way status gets updated; the user
should not need to hand-edit the table or type a status-update command for
routine cases.

If you're unsure whether an open item was actually resolved, or which row a
resolution applies to, don't guess — ask, or leave it open. The explicit
`/TBD-status <item keyword> <new status>` command exists as a manual
override for anything you didn't catch or got wrong.
