-- Generated from contracts/finance.revenue_daily.toml version 1.0.0. Do not edit.
CREATE TABLE finance.revenue_daily (
  revenue_date DATE NOT NULL,
  currency VARCHAR NOT NULL,
  revenue DECIMAL(18,4) NOT NULL,
  order_count BIGINT NOT NULL,
  invoiced_amount DECIMAL(18,4) NOT NULL,
  PRIMARY KEY (revenue_date, currency)
);
