#!/usr/bin/env python3
"""
main.py - Điểm vào của chương trình Bầu Cua Tôm Cá.

Ví dụ:
    python main.py                      # chơi trên dòng lệnh
    python main.py --gui                # chơi bằng cửa sổ đồ họa
    python main.py --name Nam --seed 7  # đặt tên, cố định random (để tái hiện kết quả)
    python main.py --demo 1000          # máy tự chơi 1000 ván, in thống kê (kiểm thử luật)
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from modules import (Dice, Game, MIN_BET, Player, START_CHIPS, Storage, ConsoleUI,
                     Symbol, load_or_create_player)
from utils import BauCuaError, QuitGame, setup_logger


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Trò chơi Bầu Cua Tôm Cá .")
    p.add_argument("--gui", action="store_true", help="giao diện tkinter")
    p.add_argument("--name", help="tên người chơi (bỏ qua bước hỏi tên)")
    p.add_argument("--chips", type=int, help=f"số chip ban đầu (mặc định {START_CHIPS})")
    p.add_argument("--data-dir", default="data", help="thư mục lưu tiến trình/lịch sử/log")
    p.add_argument("--seed", type=int, help="hạt giống random để tái hiện kết quả")
    p.add_argument("--demo", type=int, metavar="N", help="máy tự chơi N ván rồi thoát")
    p.add_argument("--new", action="store_true", help="bỏ qua tiến trình đã lưu, chơi mới")
    return p


def run_demo(rounds: int, rng: random.Random) -> None:
    """Mô phỏng: mỗi ván cược ngẫu nhiên 1-3 linh vật; in tổng kết để kiểm tra luật."""
    player, dice, wagered = Player("Demo", 10**9), Dice(rng=rng), 0
    for _ in range(rounds):
        for symbol in rng.sample(list(Symbol), rng.randint(1, 3)):
            amount = rng.randint(MIN_BET, 100)
            player.place_bet(symbol, amount)
            wagered += amount
        player.settle(dice.roll())
    net = player.chips - 10**9
    print(f"Mô phỏng {rounds} ván: tổng cược {wagered}, người chơi {net:+d} chip "
          f"({net / wagered * 100:+.2f}% trên tiền cược), thắng {player.wins}/{player.rounds} ván.")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.chips is not None and args.chips < MIN_BET:
        print(f"--chips phải >= {MIN_BET}")
        return 2
    rng = random.Random(args.seed)                 # seed=None -> ngẫu nhiên thật
    if args.seed is not None:
        random.seed(args.seed)                     # Dice mặc định dùng module random

    if args.demo is not None:
        if args.demo <= 0:
            print("--demo phải là số dương")
            return 2
        run_demo(args.demo, rng)
        return 0

    storage = Storage(Path(args.data_dir))
    logger = setup_logger(storage.log_path)
    try:
        mode = "new" if args.new else "resume" if args.gui else "ask"
        player = load_or_create_player(storage, args.name, args.chips, mode, args.gui)
        game = Game(player, storage, Dice(), logger)
        logger.info("Bắt đầu: %s, %d chip (%s)", player.name, player.chips,
                    "GUI" if args.gui else "CLI")
        if args.gui:
            from gui import run_gui                # chỉ nạp tkinter khi thật sự cần
            run_gui(game)
        else:
            ConsoleUI(game).run()
    except QuitGame:
        print("Tạm biệt!")
    except KeyboardInterrupt:
        print("\nĐã dừng.")
    except ImportError as exc:
        print(f"Không mở được giao diện đồ họa ({exc}). Hãy chạy không có --gui.")
        return 1
    except BauCuaError as exc:
        logger.error("%s", exc)
        print(f"Lỗi: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
