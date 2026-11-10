"""
utils.py - Các hàm và lớp lỗi dùng chung cho dự án Bầu Cua Tôm Cá.

Gồm 4 nhóm:
  1. Hệ thống exception riêng (quản lý lỗi)
  2. Hàm nhập liệu & kiểm tra dữ liệu đầu vào
  3. Hàm xử lý tệp (JSON ghi nguyên tử, CSV)
  4. Cấu hình logging ghi nhật ký ra tệp
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path


# ======================================================================
# 1. EXCEPTION RIÊNG
#    Tất cả kế thừa BauCuaError để main.py chỉ cần bắt một loại lỗi gốc.
# ======================================================================
class BauCuaError(Exception):
    """Lỗi gốc của toàn bộ chương trình."""


class InvalidInputError(BauCuaError):
    """Người dùng nhập sai định dạng (tên, số tiền, lệnh...)."""


class InvalidBetError(BauCuaError):
    """Cược vi phạm luật (dưới mức tối thiểu, vượt số chip...)."""


class SaveFileError(BauCuaError):
    """Không đọc/ghi được tệp, hoặc nội dung tệp bị hỏng."""


class QuitGame(BauCuaError):
    """Không phải lỗi thật: dùng để thoát vòng lặp một cách gọn gàng."""


# ======================================================================
# 2. NHẬP LIỆU & KIỂM TRA ĐẦU VÀO
# ======================================================================
def read_line(prompt: str) -> str:
    """Đọc một dòng từ bàn phím. Hết dữ liệu (Ctrl+D / pipe cạn) -> thoát game."""
    try:
        return input(prompt).strip()
    except EOFError as exc:
        raise QuitGame("Hết dữ liệu nhập.") from exc


def validate_name(name: str) -> str:
    """Tên 2-15 ký tự, chỉ gồm chữ/số/khoảng trắng (hỗ trợ tiếng Việt)."""
    name = name.strip()
    if not 2 <= len(name) <= 15:
        raise InvalidInputError("Tên phải dài 2-15 ký tự.")
    if not all(ch.isalnum() or ch == " " for ch in name):
        raise InvalidInputError("Tên chỉ được chứa chữ, số và khoảng trắng.")
    return name


def ask_name(prompt: str = "Nhập tên của bạn: ") -> str:
    """Hỏi lại cho đến khi tên hợp lệ."""
    while True:
        try:
            return validate_name(read_line(prompt))
        except InvalidInputError as exc:
            print(f"  ! {exc}")


def parse_amount(text: str, free_chips: int) -> int:
    """Đổi chuỗi thành số tiền cược. Chấp nhận số nguyên dương hoặc 'all'."""
    if text.lower() in ("all", "het", "hết"):
        return free_chips
    try:
        amount = int(text)
    except ValueError as exc:
        raise InvalidInputError(f"'{text}' không phải số tiền hợp lệ.") from exc
    if amount <= 0:
        raise InvalidInputError("Số tiền phải lớn hơn 0.")
    return amount


# ======================================================================
# 3. XỬ LÝ TỆP
# ======================================================================
def write_json_atomic(path: Path, data: dict) -> None:
    """Ghi JSON vào tệp tạm rồi đổi tên -> nếu mất điện giữa chừng, tệp cũ vẫn nguyên."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        raise SaveFileError(f"Không ghi được {path}: {exc}") from exc


def read_json(path: Path) -> dict | None:
    """Đọc JSON. Trả None nếu chưa có tệp; tệp hỏng -> đổi tên .corrupt và báo lỗi."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        quarantine(path)
        raise SaveFileError(f"Tệp {path.name} bị hỏng ({exc}); đã chuyển thành .corrupt") from exc


def quarantine(path: Path) -> None:
    """Cách ly tệp hỏng để không đọc lỗi lặp lại ở lần chạy sau."""
    try:
        path.replace(path.with_suffix(".corrupt"))
    except OSError:
        pass


def append_csv_row(path: Path, header: list[str], row: list) -> None:
    """Thêm một dòng vào CSV; tự ghi dòng tiêu đề nếu tệp mới."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if is_new:
                writer.writerow(header)
            writer.writerow(row)
    except OSError as exc:
        raise SaveFileError(f"Không ghi được {path}: {exc}") from exc


def read_csv_rows(path: Path, last: int = 10) -> list[list[str]]:
    """Đọc `last` dòng cuối của CSV (bỏ dòng tiêu đề)."""
    try:
        with path.open(encoding="utf-8", newline="") as f:
            return list(csv.reader(f))[1:][-last:]
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise SaveFileError(f"Không đọc được {path}: {exc}") from exc


# ======================================================================
# 4. LOGGING
# ======================================================================
def setup_logger(log_path: Path) -> logging.Logger:
    """Ghi nhật ký (mỗi ván, mỗi lỗi) ra tệp. Không ghi được thì im lặng bỏ qua."""
    logger = logging.getLogger("baucua")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    except OSError:
        handler = logging.NullHandler()
    logger.addHandler(handler)
    return logger
 