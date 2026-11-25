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

## 月度封账与更正

| 字段 | 类型 | 说明 |
|---|---|---|
| `period` | text | 账期，格式 `YYYY-MM`，主键 |
| `status` | text | 账期状态：`open` / `closed` |
| `correction_id` | text | 航司更正主键，撤销与重试据此关联 |
| `request_key` | text | 请求幂等键，由 `request_id` 等派生，唯一 |
| `old_fee_cents` / `new_fee_cents` | int | 封账时点原改期费与更正后改期费（分） |
| `difference_cents` | int | 更正差额 = 新改期费 − 原改期费 |
| `entry_type` | text | 分录类型：`ADJUSTMENT`（更正）/ `REVERSAL`（撤销） |
| `amount_cents` | int | 分录带符号金额（分），撤销分录为更正的相反数 |
| `snapshot_digest` | text | 封账快照的稳定 SHA-256 摘要，用于对账校验 |

分录行一经写入永不更新、永不搬迁；`(correction_id, entry_type)` 在数据库层唯一，保证更正与撤销重试都不重复入账。
