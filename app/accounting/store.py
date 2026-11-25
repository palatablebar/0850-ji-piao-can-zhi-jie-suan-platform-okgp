import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.accounting.periods import validate_period


class AccountingStore:
    """账期、更正与调整分录的存储。

    分录行（ledger_entries）一经写入永不更新、永不搬迁；幂等由
    corrections.request_key 与 ledger_entries(correction_id, entry_type)
    的唯一约束在数据库层兜底。
    """

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=8)
        connection.row_factory = sqlite3.Row
        return connection

    def init(self):
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS accounting_periods(
              period TEXT PRIMARY KEY,
              status TEXT NOT NULL CHECK(status IN ('open', 'closed')),
              created_at TEXT NOT NULL,
              closed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS period_closes(
              period TEXT PRIMARY KEY,
              entry_count INTEGER NOT NULL,
              debit_total INTEGER NOT NULL,
              credit_total INTEGER NOT NULL,
              net_total INTEGER NOT NULL,
              snapshot_digest TEXT NOT NULL,
              closed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS corrections(
              correction_id TEXT PRIMARY KEY,
              request_key TEXT UNIQUE NOT NULL,
              run_id TEXT NOT NULL,
              ticket_id TEXT NOT NULL,
              old_fee_cents INTEGER NOT NULL,
              new_fee_cents INTEGER NOT NULL,
              difference_cents INTEGER NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'REVERSED')),
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ledger_entries(
              id TEXT PRIMARY KEY,
              correction_id TEXT NOT NULL,
              entry_type TEXT NOT NULL CHECK(entry_type IN ('ADJUSTMENT', 'REVERSAL')),
              period TEXT NOT NULL,
              amount_cents INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY(correction_id) REFERENCES corrections(correction_id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_entry_correction_type
              ON ledger_entries(correction_id, entry_type);
            CREATE INDEX IF NOT EXISTS idx_entry_period ON ledger_entries(period);
            ''')

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    # ---- 账期 ----------------------------------------------------------

    def ensure_period(self, period):
        validate_period(period)
        with self.connect() as db:
            row = db.execute("SELECT * FROM accounting_periods WHERE period=?", (period,)).fetchone()
            if row is None:
                db.execute(
                    "INSERT INTO accounting_periods(period,status,created_at) VALUES(?, 'open', ?)",
                    (period, self._now()))
                row = db.execute("SELECT * FROM accounting_periods WHERE period=?", (period,)).fetchone()
        return dict(row)

    def get_period(self, period):
        with self.connect() as db:
            row = db.execute("SELECT * FROM accounting_periods WHERE period=?", (period,)).fetchone()
        return dict(row) if row else None

    def open_periods(self):
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM accounting_periods WHERE status='open' ORDER BY period").fetchall()
        return [dict(row) for row in rows]

    def current_open_period(self):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM accounting_periods WHERE status='open' ORDER BY period DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def mark_period_closed(self, period, closed_at):
        with self.connect() as db:
            db.execute(
                "UPDATE accounting_periods SET status='closed', closed_at=? WHERE period=?",
                (closed_at, period))

    # ---- 封账快照 -------------------------------------------------------

    def get_close(self, period):
        with self.connect() as db:
            row = db.execute("SELECT * FROM period_closes WHERE period=?", (period,)).fetchone()
        return dict(row) if row else None

    def insert_close(self, summary, digest, closed_at):
        with self.connect() as db:
            db.execute('''INSERT OR IGNORE INTO period_closes
                (period,entry_count,debit_total,credit_total,net_total,snapshot_digest,closed_at)
                VALUES(?,?,?,?,?,?,?)''',
                       (summary["period"], summary["entry_count"], summary["debit_total"],
                        summary["credit_total"], summary["net_total"], digest, closed_at))
        return self.get_close(summary["period"])

    # ---- 更正与分录 -----------------------------------------------------

    def find_correction_by_request(self, request_key):
        with self.connect() as db:
            row = db.execute("SELECT * FROM corrections WHERE request_key=?", (request_key,)).fetchone()
        return dict(row) if row else None

    def get_correction(self, correction_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM corrections WHERE correction_id=?", (correction_id,)).fetchone()
        return dict(row) if row else None

    def register_correction(self, request_key, run_id, ticket_id, old_fee, new_fee, difference,
                            entry_period, amount, created_at=None):
        """一个事务写入更正主记录与调整分录；重复请求返回既有记录。"""
        created_at = created_at or self._now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT * FROM corrections WHERE request_key=?", (request_key,)).fetchone()
            if existing is not None:
                return dict(existing), False
            correction_id = uuid.uuid4().hex[:12]
            db.execute('''INSERT INTO corrections
                (correction_id,request_key,run_id,ticket_id,old_fee_cents,new_fee_cents,
                 difference_cents,status,created_at)
                VALUES(?,?,?,?,?,?,?, 'ACTIVE', ?)''',
                       (correction_id, request_key, run_id, ticket_id, old_fee, new_fee,
                        difference, created_at))
            db.execute('''INSERT INTO ledger_entries
                (id,correction_id,entry_type,period,amount_cents,created_at)
                VALUES(?,?, 'ADJUSTMENT', ?,?,?)''',
                       (uuid.uuid4().hex[:12], correction_id, entry_period, amount, created_at))
        return self.get_correction(correction_id), True

    def mark_correction_reversed(self, correction_id):
        with self.connect() as db:
            db.execute("UPDATE corrections SET status='REVERSED' WHERE correction_id=?",
                       (correction_id,))

    def add_reversal_entry(self, correction_id, period, amount, created_at=None):
        """撤销分录。UNIQUE(correction_id, 'REVERSAL') 保证重复撤销不会重复入账。"""
        created_at = created_at or self._now()
        with self.connect() as db:
            try:
                db.execute('''INSERT INTO ledger_entries
                    (id,correction_id,entry_type,period,amount_cents,created_at)
                    VALUES(?,?, 'REVERSAL', ?,?,?)''',
                           (uuid.uuid4().hex[:12], correction_id, period, amount, created_at))
            except sqlite3.IntegrityError:
                return False
        return True

    def get_entry(self, correction_id, entry_type):
        with self.connect() as db:
            row = db.execute('''SELECT e.*, c.ticket_id, c.run_id
                FROM ledger_entries e JOIN corrections c ON c.correction_id=e.correction_id
                WHERE e.correction_id=? AND e.entry_type=?''',
                             (correction_id, entry_type)).fetchone()
        return dict(row) if row else None

    def list_entries(self, period):
        with self.connect() as db:
            rows = db.execute('''SELECT e.*, c.ticket_id, c.run_id
                FROM ledger_entries e JOIN corrections c ON c.correction_id=e.correction_id
                WHERE e.period=? ORDER BY e.created_at, e.id''', (period,)).fetchall()
        return [dict(row) for row in rows]

    def period_totals(self, period):
        with self.connect() as db:
            row = db.execute('''SELECT
                COUNT(*) AS entry_count,
                COALESCE(SUM(CASE WHEN amount_cents > 0 THEN amount_cents ELSE 0 END), 0) AS debit_total,
                COALESCE(SUM(CASE WHEN amount_cents < 0 THEN -amount_cents ELSE 0 END), 0) AS credit_total,
                COALESCE(SUM(amount_cents), 0) AS net_total
                FROM ledger_entries WHERE period=?''', (period,)).fetchone()
        result = dict(row)
        result["period"] = period
        return result
