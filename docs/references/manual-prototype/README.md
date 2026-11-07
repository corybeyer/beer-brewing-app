# Home Brewery Companion — Manual Prototype

This is the first runnable app, following the agreed wireframes. It is a manual trial milestone, not the finished production database or sensor system.

## Included

- Recipe library, search, recipe editor, ingredients, ordered steps, timing anchors, dependencies, and draft/published versions.
- Batch setup with preparation checks, setup notes/substitutions, preserved recipe/equipment snapshots.
- Responsive brew-day dashboard with vessel temperatures, hold timers, parallel boil additions, upcoming reminders, all steps, and simple vessel graphics.
- Manual temperature, gravity, volume, and pH entries; append-only notes and action confirmations.
- Batch review, multiple tasting records, and JSON data export.
- Persistent SQLite state. Timers derive from server start/deadline timestamps, not browser countdown state.
- No assumed HERMS route, live sensor state, or automatic hardware control.

## Run on the Raspberry Pi

Use a current 64-bit Raspberry Pi OS with Python 3.10 or newer. Extract the app directory, then:

~~~bash
cd brewery-app
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 8000
~~~

Open http://YOUR-PI-IP:8000 from a phone or computer on the home network. Replace YOUR-PI-IP with the Pi's address. The service is intended for a trusted home network; this prototype has no user authentication. No cloud hosting is required.

For development on one computer, use --host 127.0.0.1.

The default database is data/brewery.sqlite. Set BREWERY_DB to use a different absolute file path. The seed sample recipe appears only when there are no recipe records. The sample is illustrative; review quantities, water calculations, temperatures, and ingredient instructions before an actual brew.

## Manual trial

1. Open Recipes and create a revision of the sample.
2. Review ingredients and steps. Shorten hold durations for a pretend trial, then save and publish.
3. Prepare a batch and enter setup notes.
4. Start the session. Confirm strike water and mash-in; start the mash hold only after the physical action.
5. Log manual vessel readings, refresh the page, and verify that the timer persists.
6. Start a confirmed boil. Hop reminders share its start time and run alongside the boil hold.
7. Confirm completed additions, chill, and finish the brew day.
8. Review results and add tasting notes.

Acting early requires a deviation reason. Repeated identical confirmations are idempotent. A temperature reading never automatically confirms a physical action.

## Prototype boundaries

The approved three-view ERD remains the target design. This prototype uses eight compact SQLite tables and validated recipe/step snapshots; it does not yet implement all 31 logical entities. That is deliberate for the manual workflow trial.

Pending: complete BJCP catalog (only 18B example and Custom are offered), imports/OCR, explicit ingredient portion links, full source attribution fields, editable equipment profiles, packaging dates and beer-age calculations, recipe-revision tasting provenance, event-correction controls, pause/resume and reminder snoozing, live sensor gateway, background alert delivery, backup scheduling/restoration, and production migrations.

Timing alerts are evaluated when the dashboard requests state (every five seconds while open). Stored deadlines recover on restart, but the prototype does not deliver alerts when all browsers are closed or a phone is locked. Add a background scheduler/notification channel before relying on unattended reminders.

The UI does not stop physical brewing when a timer ends. The brewer confirms completion. The prototype warns when manual temperature samples are older than five minutes; this is an illustrative threshold, not a sensor safety rule.

Substitution text is preserved with batch setup; structured actual ingredient accounting is pending.

## Data preservation

Database state persists on the Pi. The archive does not ship an existing database. For a simple file backup, stop the server and copy the database file. JSON export is useful for inspection; a restore/import endpoint is not included yet.

Published recipe plans are protected by database triggers. Batch snapshots remain independent of later recipe revisions. Cross-batch action access, cyclic step dependencies, invalid measurements, and invalid tasting ratings are rejected.

## Tests

~~~bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
~~~

Four backend tests cover parallel additions and restart recovery; duplicate confirmation/cross-batch access; published-version immutability and batch snapshots; cycles, invalid references, invalid values, and repeated tastings.

See VERIFICATION.md for the recorded result and browser checks.
