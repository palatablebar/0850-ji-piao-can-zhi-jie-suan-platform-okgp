# 字段定义

| 字段 | 类型 | 说明 |
|---|---|---|
| `ticket_id` | text | 主键 |
| `passenger_id` | text | 业务字段 |
| `action` | text | 业务字段 |
| `original_fare_cents` | int | 业务字段 |
| `taxes_cents` | int | 业务字段 |
| `change_fee_cents` | int | 业务字段 |
| `refundable` | text | 业务字段 |
| `new_fare_cents` | int | 业务字段 |
| `invoice_cents` | int | 业务字段 |

空字符串、`-`、`NA`、`null` 和 `未提供` 按空值处理。金额字段在整理层转为整数分或整数最小单位；日期按 ISO 日期解析；带时间的字段按本地时间解析。标识字段保持为文本，前导零不会被去除。
