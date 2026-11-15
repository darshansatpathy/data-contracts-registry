-- Generated from contracts/sales.orders.toml version 1.2.0. Do not edit.
CREATE TABLE IF NOT EXISTS sales.orders (
  order_id STRING NOT NULL COMMENT 'Storefront order identifier.',
  customer_id STRING NOT NULL COMMENT 'Pseudonymous customer identifier.',
  amount DECIMAL(18,4) NOT NULL COMMENT 'Order total including tax, in the order currency.',
  currency STRING NOT NULL COMMENT 'ISO 4217 currency of the amount.',
  status STRING NOT NULL COMMENT 'Where the order is in its life.',
  channel STRING COMMENT 'Sales channel, mapped to a closed set.',
  ordered_at TIMESTAMP NOT NULL COMMENT 'When the order was created, UTC.',
  order_date DATE NOT NULL COMMENT 'Calendar date of ordered_at in UTC. Added in 1.2.0 for daily reporting.'
)
USING DELTA
COMMENT 'One row per customer order after cleaning and de-duplication. The source of truth for revenue.'
TBLPROPERTIES (
  'contract.version' = '1.2.0',
  'contract.owner' = 'sales-data',
  'contract.classification' = 'internal',
  'contract.tier' = '1'
);
