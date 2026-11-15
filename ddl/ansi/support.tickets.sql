-- Generated from contracts/support.tickets.toml version 0.1.0. Do not edit.
CREATE TABLE support.tickets (
  ticket_id VARCHAR NOT NULL,
  customer_id VARCHAR NOT NULL,
  subject VARCHAR NOT NULL,
  body VARCHAR,
  priority VARCHAR NOT NULL,
  opened_at TIMESTAMP NOT NULL,
  PRIMARY KEY (ticket_id),
  CHECK (priority IS NULL OR priority IN ('low', 'normal', 'high', 'urgent'))
);
