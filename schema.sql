-- D1 schema for the safeagi.ca mailing list
CREATE TABLE IF NOT EXISTS subscribers (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  email      TEXT NOT NULL UNIQUE,
  status     TEXT NOT NULL DEFAULT 'pending',   -- pending | confirmed | unsubscribed
  token      TEXT NOT NULL,                     -- used for confirm and unsubscribe links
  lang       TEXT DEFAULT 'en',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  confirmed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_status ON subscribers(status);
CREATE INDEX IF NOT EXISTS idx_token  ON subscribers(token);
