# Data extract

PAYMENTS:

| payment_id | vendor_id | amount (USD) |
|---|---|---:|
| P1001 | V12 | 730.00 |
| P1002 | V14 | 1270.00 |
| P1003 | V88 | 1370.00 |
| P1004 | V11 | 490.00 |
| P1005 | V10 | 1610.00 |
| P1006 | V13 | 1750.00 |
| P1007 | V13 | 1770.00 |
| P1008 | V99 | 1530.00 |
| P1009 | V12 | 1850.00 |
| P1010 | V77 | 260.00 |
| P1011 | V10 | 1700.00 |
| P1012 | V12 | 1880.00 |

VENDORS (approved master file):

| vendor_id | name |
|---|---|
| V10 | Vendor V10 |
| V11 | Vendor V11 |
| V12 | Vendor V12 |
| V13 | Vendor V13 |
| V14 | Vendor V14 |

Audit query under review:

```sql
SELECT p.* FROM payments p
INNER JOIN vendors v ON v.vendor_id = p.vendor_id;
```
