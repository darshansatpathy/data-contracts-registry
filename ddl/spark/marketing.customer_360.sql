-- Generated from contracts/marketing.customer_360.toml version 1.0.0. Do not edit.
CREATE TABLE IF NOT EXISTS marketing.customer_360 (
  customer_id STRING NOT NULL COMMENT 'Pseudonymous customer identifier.',
  email STRING NOT NULL COMMENT 'Email address for campaigns. Personal data.',
  segment STRING NOT NULL COMMENT 'Commercial segment assigned by sales operations.',
  marketing_opt_in BOOLEAN NOT NULL COMMENT 'Whether the customer agreed to marketing messages.',
  lifetime_value DECIMAL(18,4) NOT NULL COMMENT 'Total order amount over the customer''s life, in INR.',
  last_order_at TIMESTAMP COMMENT 'When the customer last ordered; null if they never have.'
)
USING DELTA
COMMENT 'Marketing view of each customer: segment, consent, lifetime value and last order.'
TBLPROPERTIES (
  'contract.version' = '1.0.0',
  'contract.owner' = 'marketing-data',
  'contract.classification' = 'confidential',
  'contract.tier' = '2'
);
