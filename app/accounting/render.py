import csv
import io

COLUMNS = ["period", "entry_id", "entry_type", "correction_id", "run_id",
           "ticket_id", "amount_cents", "created_at"]
HEADERS = ["账期", "分录号", "类型", "更正号", "批次号", "票号", "金额(分)", "入账时间"]


def render_ledger_csv(ledger):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADERS)
    for entry in ledger["entries"]:
        writer.writerow([entry[column] for column in COLUMNS])
    totals = ledger["totals"]
    writer.writerow([])
    writer.writerow(["账期", ledger["period"], "状态", ledger["status"],
                     "封账冻结", "是" if ledger["frozen"] else "否", "", ""])
    writer.writerow(["分录数", totals["entry_count"], "借方合计(分)", totals["debit_total"],
                     "贷方合计(分)", totals["credit_total"], "净额(分)", totals["net_total"]])
    if "close" in ledger:
        writer.writerow(["封账时间", ledger["close"]["closed_at"],
                         "快照摘要", ledger["close"]["snapshot_digest"], "", "", "", ""])
    return buffer.getvalue().encode("utf-8-sig")
