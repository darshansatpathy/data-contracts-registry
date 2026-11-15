-- Generated from contracts/sales.raw_orders.toml version 1.0.0. Do not edit.
CREATE TABLE IF NOT EXISTS sales.raw_orders (
  order_id STRING NOT NULL COMMENT 'Storefront order identifier.',
  customer_email STRING COMMENT 'Email typed at checkout. Personal data.',
  customer_id STRING NOT NULL COMMENT 'Pseudonymous customer identifier.',
  amount DECIMAL(18,4) NOT NULL COMMENT 'Order total including tax, in the order currency.',
  currency STRING NOT NULL COMMENT 'ISO 4217 currency of the amount.',
  channel STRING COMMENT 'Sales channel as the storefront names it; free text.',
  created_at TIMESTAMP NOT NULL COMMENT 'When the storefront created the order, UTC.',
  legacy_code STRING COMMENT 'Old channel code, kept until the storefront stops sending it.'
)
USING DELTA
COMMENT 'Orders exactly as the storefront emitted them, before cleaning. Kept for replay.'
TBLPROPERTIES (
  'contract.version' = '1.0.0',
  'contract.owner' = 'sales-data',
  'contract.classification' = 'confidential',
  'contract.tier' = '2'
);
