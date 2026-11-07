---
name: database-migrations
description: Add or review database schema changes for recipes, batch logs, timestamps, measurements, and deployment-safe migrations.
---

# Database migrations
1. Keep committed schema definitions and migrations versioned.
2. Never commit live database files or production backups.
3. Preserve a recipe snapshot/version for each brew session.
4. Define forward migration, backup, compatibility, and rollback strategy.
5. Test migrations from an existing populated database fixture.
