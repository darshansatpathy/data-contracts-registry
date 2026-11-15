-- Generated from contracts/finance.revenue_daily.toml version 1.0.0. Do not edit.
CREATE TABLE IF NOT EXISTS finance.revenue_daily (
  revenue_date DATE NOT NULL COMMENT 'Calendar date in UTC.',
  currency STRING NOT NULL COMMENT 'ISO 4217 currency the amounts are in.',
  revenue DECIMAL(18,4) NOT NULL COMMENT 'Sum of order amounts that day, excluding cancelled orders.',
  order_count BIGINT NOT NULL COMMENT 'Number of orders counted in revenue.',
  invoiced_amount DECIMAL(18,4) NOT NULL COMMENT 'Sum of invoice amounts issued that day.'
)
USING DELTA
COMMENT 'Revenue and order counts per day and currency, built from orders and invoices.'
TBLPROPERTIES (
  'contract.version' = '1.0.0',
  'contract.owner' = 'finance-data',
  'contract.classification' = 'internal',
  'contract.tier' = '2'
);
