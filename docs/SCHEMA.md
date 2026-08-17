# Normalized payment schema

Internal table `payments`. IEEE-CIS is not used as 871 raw columns.

| Field | Source | Notes |
|---|---|---|
| transaction_id | IEEE `TransactionID` or generated | Unique |
| timestamp | IEEE `TransactionDT` | Seconds from contest origin |
| amount | IEEE `TransactionAmt` | Must be > 0 |
| merchant_category | IEEE `ProductCD` | W / C / H / R / S |
| payment_method | IEEE `card4` + `card6` | e.g. visa_debit |
| country | IEEE `addr2` | Numeric country code |
| distance_from_home | IEEE `dist1` | Nulls filled with median |
| device_id | IEEE identity `DeviceInfo` / `id_31` | Hashed; missing → `unknown` |
| customer_id | **Derived** | Hash of `card1` |
| merchant_id | **Synthetic-stable** | Hash of `ProductCD` + `card1` bucket |
| ip_id | **Synthetic-stable** | Hash of device + `addr1` |
| beneficiary_id | **Synthetic-stable** | Hash of merchant + country |
| account_age_days | **Derived** | IEEE `D1` |
| transaction_count_1h | **Derived** | Per-customer rolling count |
| transaction_count_24h | **Derived** | Per-customer rolling count |
| avg_amount_30d | **Derived** | Per-customer rolling mean |
| amount_deviation | **Derived** | amount / avg − 1 |
| device_age_days | **Derived** | First-seen device vs current DT |
| failed_auth_count | **Synthetic** | 0 on legit; raised only by ATO |
| merchant_risk | **Derived** | Train-split fraud rate only |
| hour_of_day | **Derived** | `timestamp % 86400 / 3600` |
| beneficiary_is_new | **Derived / attack** | 1 on destination attacks |
| destination_concentration | **Derived / attack** | Share of recent pays to top dest |
| merchant_count_24h | **Derived / attack** | Distinct merchants in window |
| fraud_label | IEEE `isFraud` or 1 | Synthetic attacks labeled 1 |
| attack_family | none / family id | Not a model feature |

Null policy: required numeric fields are filled (median or 0). `amount` must remain > 0.
