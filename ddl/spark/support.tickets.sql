-- Generated from contracts/support.tickets.toml version 0.1.0. Do not edit.
CREATE TABLE IF NOT EXISTS support.tickets (
  ticket_id STRING NOT NULL COMMENT 'Help desk ticket number.',
  customer_id STRING NOT NULL COMMENT 'Pseudonymous customer identifier.',
  subject STRING NOT NULL COMMENT 'Ticket subject line as typed by the customer.',
  body STRING COMMENT 'Free text of the ticket. May contain personal data.',
  priority STRING NOT NULL COMMENT 'Priority assigned by the triage agent.',
  opened_at TIMESTAMP NOT NULL COMMENT 'When the ticket was opened, UTC.'
)
USING DELTA
COMMENT 'Support tickets from the help desk. Draft: free text may hold personal data, under review.'
TBLPROPERTIES (
  'contract.version' = '0.1.0',
  'contract.owner' = 'support-data',
  'contract.classification' = 'confidential',
  'contract.tier' = '3'
);
