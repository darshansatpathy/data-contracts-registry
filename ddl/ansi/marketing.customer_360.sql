-- Generated from contracts/marketing.customer_360.toml version 1.0.0. Do not edit.
CREATE TABLE marketing.customer_360 (
  customer_id VARCHAR NOT NULL,
  email VARCHAR NOT NULL,
  segment VARCHAR NOT NULL,
  marketing_opt_in BOOLEAN NOT NULL,
  lifetime_value DECIMAL(18,4) NOT NULL,
  last_order_at TIMESTAMP,
  PRIMARY KEY (customer_id),
  CHECK (segment IS NULL OR segment IN ('consumer', 'smb', 'enterprise'))
);
