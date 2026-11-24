import re
import unicodedata


BLANKS = {"", "-", "--", "n/a", "na", "null", "none", "未提供", "未知"}
NUMBER_WITH_GROUPING = re.compile(r"^-?\d{1,3}(?:,\d{3})+(?:\.\d+)?$")


def canonical(value) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKC", text).strip()
    if NUMBER_WITH_GROUPING.fullmatch(text):
        text = text.replace(",", "")
    if text.lower() in BLANKS:
        return ""
    return text
