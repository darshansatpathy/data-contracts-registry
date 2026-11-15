-- Generated from contracts/ml.churn_features.toml version 1.0.0. Do not edit.
CREATE TABLE ml.churn_features (
  customer_id VARCHAR NOT NULL,
  snapshot_date DATE NOT NULL,
  orders_90d BIGINT NOT NULL,
  avg_amount_90d DECIMAL(18,4),
  days_since_last_order INTEGER,
  segment VARCHAR NOT NULL,
  PRIMARY KEY (customer_id, snapshot_date),
  CHECK (segment IS NULL OR segment IN ('consumer', 'smb', 'enterprise'))
);
