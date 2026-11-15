-- Generated from contracts/ml.churn_features.toml version 1.0.0. Do not edit.
CREATE TABLE IF NOT EXISTS ml.churn_features (
  customer_id STRING NOT NULL COMMENT 'Pseudonymous customer identifier.',
  snapshot_date DATE NOT NULL COMMENT 'Date the features were computed for.',
  orders_90d BIGINT NOT NULL COMMENT 'Number of orders in the 90 days before the snapshot.',
  avg_amount_90d DECIMAL(18,4) COMMENT 'Mean order amount over the same window; null with no orders.',
  days_since_last_order INTEGER COMMENT 'Days from the last order to the snapshot; null with no orders.',
  segment STRING NOT NULL COMMENT 'Commercial segment at the snapshot date.'
)
USING DELTA
COMMENT 'Daily feature snapshot per customer for the churn model. No personal data.'
TBLPROPERTIES (
  'contract.version' = '1.0.0',
  'contract.owner' = 'ml-platform',
  'contract.classification' = 'internal',
  'contract.tier' = '2'
);
