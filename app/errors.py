from flask import jsonify


MESSAGES = {
    "EMPTY_FILE": "文件为空",
    "BLANK_FILE": "文件只有空白",
    "HEADER_ONLY": "文件只有表头",
    "HEADER_MISMATCH": "表头与本项目字段不一致",
    "UNCLOSED_QUOTE": "引号未闭合，文件已拒收",
    "TOO_MANY_ROWS": "数据行超过上限",
    "FILE_TOO_LARGE": "文件超过大小上限",
    "KEY_MISSING": "主键为空",
    "CONFLICT_DUPLICATE": "同一键存在冲突内容",
    "SAMPLE_UNKNOWN": "样例不存在",
    "STAGE_UNKNOWN": "阶段不存在",
    "RUN_NOT_FOUND": "批次不存在",
    "STALE_REVIEW": "批次已被更新，请刷新后复核",
    "GATE_BLOCKED": "存在阻断项，不能签发",
    "NOT_APPROVED": "批次尚未签发",
    "BAD_REQUEST": "请求内容不完整",
    "BAD_PERIOD": "账期格式应为 YYYY-MM",
    "BAD_FEE": "更正后改期费必须是非负整数（分）",
    "NO_DIFFERENCE": "更正后金额与原改期费一致，没有差额可入账",
    "PERIOD_NOT_FOUND": "账期不存在",
    "PERIOD_CLOSED": "账期已封账，差额只能进入当前未封账月",
    "TICKET_NOT_FOUND": "批次中找不到该票号",
    "CORRECTION_NOT_FOUND": "更正记录不存在",
    "CORRECTION_ALREADY_REVERSED": "该更正已撤销，不能重复撤销",
}


class DomainIssue(Exception):
    def __init__(self, code: str, status: int = 400, detail: str | None = None):
        self.code = code
        self.status = status
        self.detail = detail
        super().__init__(code)


def error_response(exc: DomainIssue):
    return jsonify(error=exc.detail or MESSAGES.get(exc.code, "请求无法处理"), code=exc.code), exc.status
