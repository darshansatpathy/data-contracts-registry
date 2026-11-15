-- Generated from contracts/sales.orders.toml version 1.2.0. Do not edit.
CREATE TABLE sales.orders (
  order_id VARCHAR NOT NULL,
  customer_id VARCHAR NOT NULL,
  amount DECIMAL(18,4) NOT NULL,
  currency VARCHAR NOT NULL,
  status VARCHAR NOT NULL,
  channel VARCHAR,
  ordered_at TIMESTAMP NOT NULL,
  order_date DATE NOT NULL,
  PRIMARY KEY (order_id),
  CHECK (currency IS NULL OR currency IN ('INR', 'USD', 'EUR', 'GBP')),
  CHECK (status IS NULL OR status IN ('placed', 'paid', 'shipped', 'cancelled', 'returned')),
  CHECK (channel IS NULL OR channel IN ('web', 'app', 'store', 'partner'))
);
