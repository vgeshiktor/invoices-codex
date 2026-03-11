# GitHub Project Field Mapping (Status/Owner/Week)

Date: 2026-03-10

This mapping is aligned with:
- `docs/FRONTEND_GITHUB_ISSUES.md`
- `docs/FRONTEND_PARALLEL_EXECUTION_MATRIX.md`

## 1. Project Fields

Use these Project v2 single-select fields:

1. `Status`
- `Todo`
- `In Progress`
- `Blocked`
- `In Review`
- `Done`

2. `Owner`
- `Nebula`
- `Andromeda`
- `Orion`
- `Vega`
- `Apollo`

3. `Week`
- `Week 1`
- `Week 2`
- `Week 3`
- `Week 4`
- `Week 5`
- `Week 6`
- `Week 7`
- `Week 8`
- `Week 9`
- `Week 10`

Default field values at import:
- `Status = Todo`
- `Owner = <mapped by issue id>`
- `Week = <mapped from issue milestone in issue pack>`

## 2. Owner Assignment by Issue ID

`Nebula`:
- `BE-001`
- `BE-101`
- `BE-201`
- `BE-301`
- `BE-401`

`Andromeda`:
- `BE-102`
- `BE-202`
- `BE-302`
- `BE-402`

`Orion`:
- `FE-001`
- `FE-003`
- `FE-005`
- `FE-101`
- `FE-201`
- `FE-301`
- `FE-401`
- `FE-402`
- `FE-501`
- `FE-601`
- `FE-602`
- `FE-604`

`Vega`:
- `FE-002`
- `FE-004`
- `FE-006`
- `FE-102`
- `FE-103`
- `FE-202`
- `FE-302`
- `FE-303`
- `FE-403`
- `FE-404`
- `FE-502`
- `FE-603`
- `FE-605`
- `FE-703`
- `FE-704`

`Apollo`:
- `FE-007`
- `FE-104`
- `FE-203`
- `FE-304`
- `FE-405`
- `FE-503`
- `FE-701`
- `FE-702`
- `FE-705`

## 3. Automation Script

Use:
- `scripts/sync_frontend_project_fields.sh`

What it does:
1. Ensures Project fields exist (`Status`, `Owner`, `Week`) if missing.
2. Adds imported issues to the target Project.
3. Sets Project fields for each issue using the mapping above.

Required auth scope:
- `project`

Suggested first run:
```bash
scripts/sync_frontend_project_fields.sh \
  --repo vgeshiktor/invoices-codex \
  --project-owner vgeshiktor \
  --project-number <PROJECT_NUMBER> \
  --dry-run
```
