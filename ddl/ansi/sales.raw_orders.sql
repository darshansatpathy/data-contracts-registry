-- Generated from contracts/sales.raw_orders.toml version 1.0.0. Do not edit.
CREATE TABLE sales.raw_orders (
  order_id VARCHAR NOT NULL,
  customer_email VARCHAR,
  customer_id VARCHAR NOT NULL,
  amount DECIMAL(18,4) NOT NULL,
  currency VARCHAR NOT NULL,
  channel VARCHAR,
  created_at TIMESTAMP NOT NULL,
  legacy_code VARCHAR,
  PRIMARY KEY (order_id),
  CHECK (currency IS NULL OR currency IN ('INR', 'USD', 'EUR', 'GBP'))
);
