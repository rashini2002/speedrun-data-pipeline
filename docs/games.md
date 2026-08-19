## Confirmed run object shape (from Celeste Any% leaderboard)
- id: unique run ID
- game, category: linking IDs
- players: array of {rel, id, uri} — only user ID, NOT name/country.
  Requires separate /users/{id} call to resolve country.
- date: run date (string, sometimes null for old runs)
- times.primary_t: run time in seconds (float) — use this for calculations
- status.status: "verified" / "rejected" / "new" — filter to "verified" only
- Category types: filter to "type": "per-game" only (per-level categories
  don't expose a direct leaderboard the same way)