# 机票残值结算台

航旅结算专员处理残值抵扣与税费分离的本地工作台。样例、规则和复核记录都在项目内，不依赖外部服务。

## 启动

```bash
docker compose up --build
```

打开 `http://127.0.0.1:${PORT:-18520}`。默认端口见 `docker-compose.yml`。

## 验证

```bash
docker compose exec -T app pytest -q
docker compose config --quiet
```

## 操作

1. 在左侧选阶段，查看采信、整理、计算、判定和对账结果。
2. 选择 `dirty` 样例观察坏行和隔离原因。
3. 换 `clean` 样例执行批次，填写复核意见后签发。
4. 下载证据 JSON，核对来源摘要、指标和签发版本。
5. 在「月度封账与航司更正」面板选择账期查看结算账；对已签发批次登记航司改期费更正，差额自动进入当前未封账月，旧账金额保持不变。
6. 封账后下载该账期结算账（CSV/JSON，含冻结快照）；已封账账期的更正撤销会把反向差额计入当期，未封账则在同月抵消。

业务规则见 `docs/BUSINESS-RULES.md`，字段定义见 `docs/DATA-DICTIONARY.md`。

### 封账与更正接口

| 接口 | 说明 |
|---|---|
| `POST /api/accounting/corrections` | 登记更正（`run_id`、`ticket_id`、`new_fee_cents`、`request_id`），同 `request_id` 重试幂等 |
| `POST /api/accounting/corrections/{id}/reverse` | 撤销更正，按原账期封账状态决定同月抵消或进当期 |
| `POST /api/accounting/periods/{period}/close` | 按月封账并写快照，重试幂等 |
| `GET /api/accounting/periods/{period}/ledger?format=csv\|json` | 下载指定账期结算账 |
