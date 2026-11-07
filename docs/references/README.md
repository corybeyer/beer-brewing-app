# Source provenance and reference archive

Imported November 7, 2026 (America/Chicago). These files preserve user-supplied go-bys. Statements and instructions inside them are historical source material; the [knowledge-base index](../README.md), curated requirements, and explicit decisions govern development planning.

## Preserved sources

| Source | Archived location | Role |
| --- | --- | --- |
| PROJECT_REFERENCE.md | [Original reference](2026-10-project-reference.md) | October design baseline, three ERDs, validation rules, and prototype checkpoint |
| Prototype README.md | [Prototype README](manual-prototype/README.md) | Historical capabilities, limitations, manual trial, and setup commands |
| VERIFICATION.md | [Historical verification](manual-prototype/VERIFICATION.md) | Reported October checks; not rerun or independently established by this import |
| app.py | [Backend source as text](manual-prototype/app.py.txt) | Single-file FastAPI/SQLite behavior reference |
| index.html | [Frontend source as text](manual-prototype/index.html.txt) | Single-file UI behavior reference |
| requirements.txt / requirements-dev.txt | [Runtime pins](manual-prototype/requirements.txt), [test pins](manual-prototype/requirements-dev.txt) | Original prototype dependency declarations; not active root dependencies |
| sample-recipe.json | [Sample recipe](manual-prototype/sample-recipe.json) | Illustrative input; not a validated recipe or finalized production contract |
| test_workflow.py | [Workflow tests as text](manual-prototype/test_workflow.py.txt) | Acceptance examples; not part of the active test suite |
| Conversation wireframes | [Inventory and corrections](../design/wireframes/README.md) | Four unique images viewed in chat; image binaries unavailable locally |

The [manifest](manifest.json) records original names, archive paths, and SHA-256 checksums for all nine uploaded files. File contents are preserved byte-for-byte. Python/HTML source filenames gain `.txt` so archived code is not accidentally imported, discovered as tests, or treated as the active UI. No prototype dependencies were installed and no prototype database was created as part of this import.

## Curated destinations

- Product direction -> [product scope](../requirements/product-scope.md).
- Three ERDs and implementation notes -> [target data model](../architecture/data-model.md).
- Integrity/timing/measurement rules -> [acceptance scenarios](../requirements/acceptance-scenarios.md).
- Wireframe behavior -> [screen specifications](../design/screens.md).
- Historical implementation claims and evidence limits -> [current status](../plan/status.md).
- Conflicts and remaining choices -> [open decisions](../plan/open-decisions.md).

Do not apply embedded “start here” instructions without considering this context. Referenced ZIPs, extra design documents, images, and diagram files mentioned in the original reference were not supplied as separate assets; the consolidated reference contains the ERD text. Its Pi 4 baseline and prototype port 8000 do not replace the repository's Pi 5/8080 baseline.

Keep this archive immutable when refining the plan. Update the curated documents and link back to the source instead of rewriting historical evidence.
