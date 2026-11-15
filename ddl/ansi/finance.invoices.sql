-- Generated from contracts/finance.invoices.toml version 2.0.0. Do not edit.
CREATE TABLE finance.invoices (
  invoice_id VARCHAR NOT NULL,
  order_id VARCHAR NOT NULL,
  amount DECIMAL(18,4) NOT NULL,
  currency VARCHAR NOT NULL,
  issued_on DATE NOT NULL,
  paid_on DATE,
  status VARCHAR NOT NULL,
  PRIMARY KEY (invoice_id),
  CHECK (currency IS NULL OR currency IN ('INR', 'USD', 'EUR', 'GBP')),
  CHECK (status IS NULL OR status IN ('open', 'paid', 'void', 'overdue'))
);
