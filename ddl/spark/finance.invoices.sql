-- Generated from contracts/finance.invoices.toml version 2.0.0. Do not edit.
CREATE TABLE IF NOT EXISTS finance.invoices (
  invoice_id STRING NOT NULL COMMENT 'Invoice number from the finance system.',
  order_id STRING NOT NULL COMMENT 'The order this invoice was issued for.',
  amount DECIMAL(18,4) NOT NULL COMMENT 'Invoiced amount in the invoice currency.',
  currency STRING NOT NULL COMMENT 'ISO 4217 currency of the invoice.',
  issued_on DATE NOT NULL COMMENT 'Date the invoice was issued.',
  paid_on DATE COMMENT 'Date payment was received; null while unpaid.',
  status STRING NOT NULL COMMENT 'Receivable status of the invoice.'
)
USING DELTA
COMMENT 'One row per invoice issued for an order. Used for receivables and month-end close.'
TBLPROPERTIES (
  'contract.version' = '2.0.0',
  'contract.owner' = 'finance-data',
  'contract.classification' = 'confidential',
  'contract.tier' = '1'
);
