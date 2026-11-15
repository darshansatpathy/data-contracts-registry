-- Generated from contracts/sales.legacy_orders.toml version 3.0.0. Do not edit.
CREATE TABLE IF NOT EXISTS sales.legacy_orders (
  legacy_order_no STRING NOT NULL COMMENT 'Order number in the retired system.'
)
USING DELTA
COMMENT 'Orders from the platform that was switched off in 2025. Kept only as a record of the retirement.'
TBLPROPERTIES (
  'contract.version' = '3.0.0',
  'contract.owner' = 'sales-data',
  'contract.classification' = 'internal',
  'contract.tier' = '3'
);
