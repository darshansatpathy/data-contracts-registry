-- Generated from contracts/sales.customers.toml version 1.1.0. Do not edit.
CREATE TABLE IF NOT EXISTS sales.customers (
  customer_id STRING NOT NULL COMMENT 'Pseudonymous customer identifier.',
  email STRING NOT NULL COMMENT 'Login email address. Personal data.',
  full_name STRING COMMENT 'Name as entered by the customer. Personal data.',
  country STRING NOT NULL COMMENT 'ISO 3166 alpha-2 country of the billing address.',
  segment STRING NOT NULL COMMENT 'Commercial segment assigned by sales operations.',
  created_at TIMESTAMP NOT NULL COMMENT 'When the account was created, UTC.',
  marketing_opt_in BOOLEAN NOT NULL COMMENT 'Whether the customer agreed to marketing messages.'
)
USING DELTA
COMMENT 'One row per registered customer. Holds personal data; access is limited and audited.'
TBLPROPERTIES (
  'contract.version' = '1.1.0',
  'contract.owner' = 'sales-data',
  'contract.classification' = 'restricted',
  'contract.tier' = '1'
);
