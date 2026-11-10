"""
modules.py - Các lớp chính (OOP) của game Bầu Cua Tôm Cá.

Sơ đồ lớp:
    Symbol (Enum)        : 6 linh vật
    Dice                 : xúc xắc, dùng random
    RoundResult          : kết quả một ván (dữ liệu thuần)
    Player               : chip, cược đang chờ, thống kê
    Storage              : lưu/đọc tiến trình (JSON) + lịch sử (CSV)
    Game                 : điều phối một ván: xóc -> tính tiền -> lưu -> log
    ConsoleUI            : giao diện dòng lệnh (menu lệnh, nhập liệu)
"""
from __future__ import annotations

import logging
import random
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from utils import (BauCuaError, InvalidBetError, InvalidInputError, QuitGame,
                   SaveFileError, append_csv_row, ask_name, parse_amount,
                   quarantine, read_csv_rows, read_json, read_line, write_json_atomic)

START_CHIPS = 2000   
MIN_BET = 50         

# Linh vật

class Symbol(Enum):
    """6 mặt của xúc xắc. Mỗi mặt có: tên hiển thị, biểu tượng (cho GUI), từ khóa gõ."""
    BAU = ("Bau", "🎃", "bau")
    CUA = ("Cua", "🦀", "cua")
    TOM = ("Tom", "🦐", "tom")
    CA = ("Ca", "🐟", "ca")
    GA = ("Ga", "🐓", "ga")
    NAI = ("Nai", "🦌", "nai")

    def __init__(self, label: str, icon: str, key: str) -> None:
        self.label, self.icon, self.key = label, icon, key

    def __str__(self) -> str:
        return self.label

    @classmethod
    def parse(cls, text: str) -> "Symbol":
        """Nhận số 1-6 hoặc tên (có/không dấu). Sai -> InvalidInputError."""
        text = text.strip().lower()
        members = list(cls)
        if text.isdigit() and 1 <= int(text) <= len(members):
            return members[int(text) - 1]
        for m in members:
            if text in (m.key, m.label.lower()):
                return m
        raise InvalidInputError(
            f"'{text}' không phải linh vật (dùng 1-6 hoặc bau/cua/tom/ca/ga/nai).")

# Xúc xắc
class Dice:
    """3 viên xúc xắc. Cho phép truyền `rng` riêng để kiểm thử có kết quả cố định."""

    def __init__(self, count: int = 3, rng: random.Random | None = None) -> None:
        self.count = count
        self.rng = rng or random

    def roll(self) -> list[Symbol]:
        """Xóc: mỗi viên ra ngẫu nhiên một trong 6 linh vật."""
        return [self.rng.choice(list(Symbol)) for _ in range(self.count)]

# Kết quả ván & người chơi

@dataclass
class RoundResult:
    dice: list[Symbol]                          # 3 mặt vừa xóc
    lines: list[tuple[Symbol, int, int]]        # (linh vật, tiền cược, thắng/thua)
    net: int                                    # tổng thắng/thua của ván
    bets: dict[Symbol, int] | None = None 

class Player:
    """Người chơi: giữ chip, các cược đang chờ xóc và thống kê."""

    def __init__(self, name: str, chips: int = START_CHIPS, rounds: int = 0,
                 wins: int = 0, best_win: int = 0) -> None:
        self.name, self.chips = name, chips
        self.rounds, self.wins, self.best_win = rounds, wins, best_win
        self.bets: dict[Symbol, int] = {}

    @property
    def free_chips(self) -> int:
        """Chip chưa dùng để cược trong lượt hiện tại."""
        return self.chips - sum(self.bets.values())

    @property
    def win_rate(self) -> float:
        return self.wins / self.rounds * 100 if self.rounds else 0.0
    
    @property
    def is_broke(self) -> bool:
        return self.chips < MIN_BET
    def place_bet(self, symbol: Symbol, amount: int) -> None:
        """Đặt (hoặc cộng thêm) cược. Kiểm tra mức tối thiểu và số chip còn lại."""
        if amount < MIN_BET:
            raise InvalidBetError(f"Cược tối thiểu là {MIN_BET} chip.")
        if amount > self.free_chips:
            raise InvalidBetError(f"Bạn chỉ còn {self.free_chips} chip để cược.")
        self.bets[symbol] = self.bets.get(symbol, 0) + amount

    def clear_bets(self) -> None:
        self.bets = {}

    def settle(self, dice: list[Symbol]) -> RoundResult:
        counts = Counter(dice)
        lines = []
        for symbol, amount in self.bets.items():
            hits = counts[symbol]
            delta = amount * hits if hits else -amount
            lines.append((symbol, amount, delta))
        net = sum(delta for _, _, delta in lines)
        
        old_bets = self.bets.copy() 
        
        self.chips += net
        self.rounds += 1
        if net > 0:
            self.wins += 1
            self.best_win = max(self.best_win, net)
        
        self.bets = {}  
        
        return RoundResult(dice, lines, net, bets=old_bets)

    def to_dict(self) -> dict:
        return {"name": self.name, "chips": self.chips, "rounds": self.rounds,
                "wins": self.wins, "best_win": self.best_win}


# ======================================================================
# Lưu trữ
# ======================================================================
class Storage:
    """Quản lý thư mục dữ liệu: tiến trình (JSON), lịch sử (CSV)."""
    HISTORY_HEADER = ["thoi_gian", "van", "cuoc", "ket_qua", "thang_thua", "chip_con"]

    def __init__(self, data_dir: Path) -> None:
        self.dir = Path(data_dir)
        self.save_path = self.dir / "baucua_save.json"
        self.history_path = self.dir / "baucua_history.csv"
        self.log_path = self.dir / "baucua.log"

    def save(self, player: Player) -> None:
        write_json_atomic(self.save_path, player.to_dict())

    def load(self) -> Player | None:
        """Đọc tiến trình; kiểm tra từng trường để chống dữ liệu bị sửa/hỏng."""
        data = read_json(self.save_path)
        if data is None:
            return None
        try:
            player = Player(str(data["name"]), int(data["chips"]), int(data["rounds"]),
                            int(data["wins"]), int(data["best_win"]))
            if player.chips < 0 or player.rounds < 0 or not 0 <= player.wins <= player.rounds:
                raise ValueError("số liệu vô lý")
            return player
        except (KeyError, TypeError, ValueError) as exc:
            quarantine(self.save_path)
            raise SaveFileError(f"Tệp lưu sai nội dung ({exc}); đã chuyển thành .corrupt") from exc

    def log_round(self, round_no: int, result: RoundResult, chips: int) -> None:
        from datetime import datetime
        append_csv_row(self.history_path, self.HISTORY_HEADER, [
            datetime.now().isoformat(timespec="seconds"), round_no,
            "; ".join(f"{s.label}:{a}" for s, a, _ in result.lines),
            ", ".join(s.label for s in result.dice), result.net, chips])

    def read_history(self, last: int = 10) -> list[list[str]]:
        return read_csv_rows(self.history_path, last)

# Game: điều phối một ván

class Game:
    """Nối Player + Dice + Storage. Dùng chung cho cả giao diện CLI và GUI."""

    def __init__(self, player: Player, storage: Storage, dice: Dice | None = None,
                 logger: logging.Logger | None = None) -> None:
        self.player, self.storage = player, storage
        self.dice = dice or Dice()
        self.log = logger or logging.getLogger("baucua")

    def play_round(self) -> RoundResult:
        """Một ván: kiểm tra có cược -> xóc -> tính tiền -> lưu tệp -> ghi log."""
        if not self.player.bets:
            raise InvalidBetError("Bạn chưa đặt cược nào.")
        result = self.dice.roll()
        outcome = self.player.settle(result)
        self.log.info("Ván %d: ra [%s], thắng/thua %+d, còn %d chip", self.player.rounds,
                      ", ".join(map(str, outcome.dice)), outcome.net, self.player.chips)
        try:                                    # lỗi ghi tệp không được làm sập game
            self.storage.log_round(self.player.rounds, outcome, self.player.chips)
            self.storage.save(self.player)
        except SaveFileError as exc:
            self.log.error("%s", exc)
            print(f"  (Cảnh báo: {exc})")
        return outcome

    def restart(self) -> None:
        """Chơi lại từ đầu khi hết tiền (giữ nguyên tên)."""
        self.player.chips = START_CHIPS
        self.player.clear_bets()
        self.log.info("Người chơi bắt đầu lại với %d chip", START_CHIPS)
        try:
            self.storage.save(self.player)
        except SaveFileError as exc:
            self.log.error("%s", exc)
            print("Cảnh báo : {exc}")

# Giao diện dòng lệnh

HELP_TEXT = f"""
=== BẦU CUA TÔM CÁ ===
Linh vật: """ + "  ".join(f"{i}.{s}" for i, s in enumerate(Symbol, 1)) + f"""
Lệnh:
  <linh vật> <tiền>  đặt cược, vd: 'cua 50', '3 100', 'ga all'
  lac (hoặc Enter)   xóc xúc xắc
  huy                hủy các cược đã đặt
  tk                 xem thống kê      ls  xem 10 ván gần nhất
  h                  xem hướng dẫn     q   lưu và thoát
Luật: trúng 1 con ăn 1x, 2 con ăn 2x, 3 con ăn 3x tiền cược; trượt mất cược.
Cược tối thiểu {MIN_BET} chip. Đây là chip ảo, chỉ để giải trí.
"""


class ConsoleUI:
    """Vòng lặp: hiện trạng thái -> đọc lệnh -> kiểm tra -> thực hiện."""

    def __init__(self, game: Game) -> None:
        self.game = game

    def show_stats(self) -> None:
        p = self.game.player
        print(f"\n[Thống kê] {p.name}: {p.chips} chip | {p.rounds} ván | "
              f"thắng {p.wins} ({p.win_rate:.0f}%) | thắng lớn nhất {p.best_win}")

    def show_history(self) -> None:
        rows = self.game.storage.read_history()
        if not rows:
            print("  (Chưa có lịch sử)")
        for r in rows:
            print(f"  ván {r[1]:>3} | {r[3]:<16} | {int(r[4]):+5d} | còn {r[5]}")

    def show_round(self, outcome: RoundResult) -> None:
        print("\n>>> KẾT QUẢ: " + "  |  ".join(map(str, outcome.dice)))
        for symbol, amount, delta in outcome.lines:
            hits = outcome.dice.count(symbol)
            note = f"trúng {hits} con" if hits else "trượt"
            print(f"    {symbol.label:<4} cược {amount:>4} -> {note:<12} {delta:+d}")
        word = "THẮNG" if outcome.net > 0 else "THUA" if outcome.net < 0 else "HÒA"
        print(f">>> {word} {abs(outcome.net)} chip. Còn {self.game.player.chips} chip. "
              "Bắt đầu lượt đặt cược mới.")

    def handle(self, line: str) -> None:
        """Xử lý một lệnh. Ném InvalidInputError/InvalidBetError nếu sai."""
        player, cmd = self.game.player, line.strip().lower()
        if cmd in ("q", "quit"):
            raise QuitGame
        if cmd in ("", "lac", "lắc"):
            self.show_round(self.game.play_round())
        elif cmd in ("huy", "hủy"):
            player.clear_bets()
            print("  Đã hủy các cược.")
        elif cmd == "tk":
            self.show_stats()
        elif cmd == "ls":
            self.show_history()
        elif cmd in ("h", "help", "?"):
            print(HELP_TEXT)
        else:
            parts = line.split()
            if len(parts) != 2:
                raise InvalidInputError("Cú pháp: <linh vật> <tiền>. Gõ 'h' để xem hướng dẫn.")
            player.place_bet(Symbol.parse(parts[0]), parse_amount(parts[1], player.free_chips))
            print("  Cược hiện tại: " + ", ".join(f"{s} {a}" for s, a in player.bets.items())
                  + f" (còn {player.free_chips} chip)")

    def run(self) -> None:
        player = self.game.player
        print(HELP_TEXT)
        try:
            while True:
                if player.chips < MIN_BET:
                    print(f"\nBạn đã hết chip sau {player.rounds} ván.")
                    if read_line("Chơi lại với 1000 chip? (y/n): ").lower().startswith("y"):
                        self.game.restart()
                        continue
                    break
                try:
                    self.handle(read_line(f"\n[{player.name} | {player.chips} chip] đặt cược > "))
                except (InvalidInputError, InvalidBetError) as exc:
                    print(f"  ! {exc}")
                    self.game.log.warning("Nhập sai: %s", exc)
        except QuitGame:
            print("\nĐang lưu và thoát...")
        finally:
            try:
                self.game.storage.save(player)
            except SaveFileError as exc:
                print(f"! {exc}")
            self.show_stats()


def load_or_create_player(storage: Storage, name: str | None, chips: int | None,
                          mode: str = "ask", gui: bool = False) -> Player:
    """
    Mở tiến trình đã lưu hoặc tạo người chơi mới.
      mode="ask"    : hỏi người dùng có tiếp tục game cũ không (CLI)
      mode="resume" : tự động tiếp tục nếu có tệp lưu (GUI)
      mode="new"    : bỏ qua tệp lưu, chơi mới
    """
    saved = None
    if mode != "new":
        try:
            saved = storage.load()
        except SaveFileError as exc:
            print(f"! {exc}\n  Bắt đầu game mới.")
    if saved:
        if mode == "resume":
            return saved
        answer = read_line(f"Tìm thấy game của '{saved.name}' ({saved.chips} chip, "
                           f"{saved.rounds} ván). Tiếp tục? (y/n): ")
        if answer.lower().startswith("y"):
            return saved
    start_chips = chips if chips is not None else START_CHIPS
    return Player(name or ("Người chơi" if gui else ask_name()), start_chips)


__all__ = ["Symbol", "Dice", "Player", "RoundResult", "Storage", "Game", "ConsoleUI",
           "load_or_create_player", "START_CHIPS", "MIN_BET", "BauCuaError"]
