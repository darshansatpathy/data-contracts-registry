-- Generated from contracts/sales.customers.toml version 1.1.0. Do not edit.
CREATE TABLE sales.customers (
  customer_id VARCHAR NOT NULL,
  email VARCHAR NOT NULL,
  full_name VARCHAR,
  country VARCHAR NOT NULL,
  segment VARCHAR NOT NULL,
  created_at TIMESTAMP NOT NULL,
  marketing_opt_in BOOLEAN NOT NULL,
  PRIMARY KEY (customer_id),
  CHECK (segment IS NULL OR segment IN ('consumer', 'smb', 'enterprise'))
);
