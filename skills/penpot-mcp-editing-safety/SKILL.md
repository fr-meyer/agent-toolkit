---
name: "penpot-mcp-editing-safety"
description: "Use when editing Penpot files through MCP; preserve manual editability and verify current-page changes safely."
---

# Penpot MCP Editing Safety

## Goal

Edit Penpot files through MCP without damaging the human's ability to select, move, resize, and edit the resulting objects manually.

The default posture is editability-first. Export fidelity is secondary unless the user explicitly asks for an export-only copy.

## Scope

Use this skill for Penpot MCP work such as:

- inspecting a Penpot file or page before automated edits
- changing text, photos, masks, arrows, circles, boards, or layout
- repairing locked, blocked, misplaced, duplicated, or unselectable objects
- exporting Penpot frames while checking whether export output is trustworthy
- diagnosing stale layers, hidden overlays, nested boards, clipping-mask traps, or page-switch mistakes

Do not use this skill for general frontend UI design, graphic critique, or copywriting unless Penpot MCP automation is part of the task. Pair it with design, copy, or review skills when those are the main job.

## Core Rules

- Preserve manual editability in the working Penpot file.
- Never use visible SVG text overlays as the editable source of truth.
- Do not claim editability from metadata alone. Prove it by testing movement on the current page.
- Do not trust PNG export as proof that native Penpot text is correct. Some Penpot/plugin/export paths can drop, cache, or under-render native text.
- Do not rerun a timed-out or uncertain write batch blindly. Inspect state first.
- Do one bounded page or object group per write call unless the operation is trivial and reversible.
- Keep project-private names, paths, credentials, and host details out of reusable procedures and generated skill artifacts.

## Workflow

### 1. Establish the edit target

Before writing anything, identify:

- the Penpot file name and current page
- the page or pages the user wants changed
- the exact board/frame/object group to edit
- whether the user wants a working editable file, an export-only output, or both
- whether text/copy has already been approved
- which objects must remain manually movable, such as photos, masks, circles, arrows, and text

If the user is asking for guest-facing, client-facing, legal, medical, financial, or otherwise sensitive text changes, show the exact proposed text first and wait for approval before painting it into Penpot.

### 2. Load only the API details you need

If the relevant Penpot MCP/API behavior is not already known in the current turn, read the Penpot high-level overview once and use `penpot_api_info` for the specific types or members needed.

Prefer simple API calls first. Add more complex traversal, logging, or recovery code only when the simple approach does not answer the question safely.

### 3. Inspect before writing

Run an object-structure audit before edits. At minimum, inspect:

- all pages and the current page name/id
- visible top-level boards and export frames
- parent/child hierarchy for the intended active board
- `hidden`, `visible`, and `blocked` on each active object and its ancestors
- active object names, parent names, bounds, and parent indexes
- hidden backups, prototypes, source banks, and duplicate layer names
- loose page-level objects that spatially overlap the active board but are not descendants of it
- large visible shapes or SVG/raw groups that could intercept clicks
- clipping masks or mask boards that contain objects the user expects to move independently

Do not audit only board descendants. Loose root-level objects can still cover or block the active board in the browser.

### 4. Treat page switching as asynchronous

When switching pages with Penpot automation:

1. call `openPage(targetPage)`
2. stop that tool call
3. run a follow-up call that verifies `penpot.currentPage.name` and `penpot.currentPage.id`
4. write only after the current page is confirmed

Do not open a page and immediately edit it in the same call unless the API/tooling has already proven that page switching is synchronous in this environment.

### 5. Keep object structure editable

For editable working files:

- keep visible text as native Penpot text
- keep target circles as selectable groups containing their underlay and stroke
- keep arrows as selectable groups containing underlay, route stroke, and arrowhead parts
- keep photos in editable mask frames with the complete source image available as a child or nearby source layer
- keep movable circles, arrows, and labels outside photo mask frames unless they are intentionally clipped with the photo
- avoid full-page overlays in front of editable content
- do not lock/block objects unless the user explicitly asks for protection
- avoid extra wrapper boards around the actual guide/export frame when the human needs to edit the frame directly
- move source banks and hidden backups away from the active edit surface, or make them clearly hidden through ancestors

If an export-safe workaround is needed, create it in a separate export copy or hidden export-only layer after the user approves that tradeoff. The working file must keep native editable objects.

### 6. Write in bounded passes

Before each write pass, state what kind of edit is being made.

During the write pass:

- edit one page or one coherent object group at a time
- preserve absolute geometry when moving objects out of bad parents
- store reversible notes in plugin data for nontrivial geometry/path transformations when useful
- prefer renaming stale objects as hidden backups over deleting them unless deletion is explicitly requested or obviously safe
- after timeout, reconnect, or plugin error, run a lightweight state probe before continuing

Do not use stale IDs from earlier pages or hidden backups unless you re-verified they still belong to the active visible object.

### 7. Verify editability on the current page

For every page touched, open that page and verify `penpot.currentPage` before testing.

Then nudge-and-restore representative active objects:

- one photo or mask frame
- one target circle/group or arrow group
- one native text layer

The test is:

1. record `x` and `y`
2. set `x + 1`, `y + 1`
3. confirm the coordinates changed
4. restore the original coordinates
5. confirm they restored

Also verify:

- zero active visible objects are blocked unless intentionally protected
- zero relevant objects have blocked ancestors
- no loose root-level text/SVG/overlay overlaps the active board unexpectedly
- hidden backups and source banks are not covering the active edit surface
- the browser should be refreshed before human QA if stale rendering was observed

Only after this current-page movement test passes should you say that objects are movable/editable at the document level.

### 8. Verify visuals without overtrusting export

Use Penpot export for photos, shapes, arrows, layout, and gross visual checks.

For native text, distinguish clearly:

- browser-editable text state
- object-tree text characters/bounds
- PNG/SVG export rendering

If export omits or caches native text, do not use export as the final truth. Ask for or inspect the refreshed Penpot browser view when visual text placement is disputed.

### 9. Report honestly

When finishing, tell the user:

- which pages/objects were touched
- what was repaired or changed structurally
- what editability tests passed on the current page
- what was not changed
- what remains browser-QA only
- whether a refresh is needed

Do not say "fixed" or "editable" unless the current-page nudge-and-restore gate passed for representative objects on the relevant pages.

## Failure Patterns To Watch

- Duplicate layer names where a lookup hits a hidden backup instead of the visible active object.
- Hidden parent groups whose children remain visible or selectable through stale browser state.
- Root-level text or SVG layers covering an active board while board-descendant audits pass.
- Target circles trapped inside photo mask frames when the user expects independent movement.
- Nested guide/export frames inside wrapper boards that make the human edit the wrong container.
- Page switches that complete after the script returns.
- Native Penpot text that is editable in the browser but absent or stale in plugin PNG export.

## Completion Checklist

Before final response:

- the active page was verified after any page switch
- the intended active board/frame was identified by visible hierarchy, not only by name
- hidden/backup/prototype/source-bank layers were excluded from active edits
- loose overlapping page-level text/SVG/overlay layers were checked
- visible working text remains native Penpot text
- photos, target groups, arrows, and text remain manually selectable/movable where expected
- current-page nudge-and-restore passed for representative objects on each touched page
- export caveats are clearly separated from browser/editability truth
