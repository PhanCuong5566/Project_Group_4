"""
gui.py - Giao diện đồ họa đơn giản (tkinter) cho Bầu Cua Tôm Cá.

Luồng: đặt cược -> bấm "XÓC!" -> random 3 xúc xắc -> cộng/trừ chip
       -> tự động sang lượt đặt cược mới.
Luật chơi nằm hết trong modules.Game; file này chỉ lo hiển thị và nút bấm.
"""
import random
import tkinter as tk
from tkinter import messagebox

from modules import Game, Symbol
from utils import BauCuaError


class App:
    STEPS = (50, 100, 200)           # các mức cược mỗi lần bấm
    def __init__(self, root: tk.Tk, game: Game) -> None:
        self.root, self.game = root, game
        root.title("Bầu Cua Tôm Cá")
        root.resizable(False, False)

        self.chips_var = tk.StringVar()
        self.msg_var = tk.StringVar(value="Chọn mức cược rồi bấm vào linh vật để đặt.")
        self.step_var = tk.IntVar(value=self.STEPS[0])
        self.last_bets = {}

        tk.Label(root, textvariable=self.chips_var, font=("Arial", 18, "bold"),
                 fg="#b8860b").pack(pady=(12, 4))

        step_frame = tk.Frame(root)
        step_frame.pack()
        tk.Label(step_frame, text="Mức cược mỗi lần bấm:").pack(side="left")
        for s in self.STEPS:
            tk.Radiobutton(step_frame, text=str(s), value=s, variable=self.step_var).pack(side="left")

        # Lưới 6 linh vật (3 cột x 2 hàng)
        board = tk.Frame(root)
        board.pack(padx=14, pady=10)
        self.symbol_buttons = []
        for i, symbol in enumerate(Symbol):
            btn = tk.Button(board, width=9, height=4, font=("Arial", 14),
                            command=lambda s=symbol: self.place_bet(s))
            btn.grid(row=i // 3, column=i % 3, padx=5, pady=5)
            self.symbol_buttons.append(btn)

        # 3 ô xúc xắc
        dice_frame = tk.Frame(root)
        dice_frame.pack(pady=4)
        self.dice_labels = [tk.Label(dice_frame, text="❓", font=("Arial", 36), width=3,
                                     relief="groove") for _ in range(3)]
        for lbl in self.dice_labels:
            lbl.pack(side="left", padx=6)

        tk.Label(root, textvariable=self.msg_var, font=("Arial", 12), wraplength=340,
                 height=3).pack(padx=10)

        ctrl = tk.Frame(root)
        ctrl.pack(pady=(0, 14))
        self.clear_btn = tk.Button(ctrl, text="Xóa cược", width=10, command=self.clear_bets)
        self.clear_btn.pack(side="left", padx=6)
        self.roll_btn = tk.Button(ctrl, text="🎲 XÓC!", width=12, height=2,
                                  font=("Arial", 14, "bold"), bg="#d9534f", fg="white",
                                  command=self.roll)
        self.roll_btn.pack(side="left", padx=6)
        self.refresh()

    # ---- hiển thị -----------------------------------------------------
    def refresh(self) -> None:
        p = self.game.player
        self.chips_var.set(f"💰 {p.name}: {p.chips} chip")
        current_bets = p.bets if p.bets else self.last_bets
        for symbol, btn in zip(Symbol, self.symbol_buttons):
            bet = p.bets.get(symbol, 0)
            btn.config(text=f"{symbol.icon}\n{symbol.label}\n" + (f"Cược: {bet}" if bet else ""))

    def set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for b in self.symbol_buttons + [self.roll_btn, self.clear_btn]:
            b.config(state=state)

    # ---- hành động ----------------------------------------------------
    def place_bet(self, symbol: Symbol) -> None:
        if self.last_bets and not self.game.player.bets:
            self.last_bets = {} 
        try:
            self.game.player.place_bet(symbol, self.step_var.get())
        except BauCuaError as exc:
            self.msg_var.set(str(exc))
            return
        self.msg_var.set(f"Còn {self.game.player.free_chips} chip chưa cược.")
        self.refresh()

    def clear_bets(self) -> None:
        self.game.player.clear_bets()
        self.msg_var.set("Đã xóa cược.")
        self.refresh()

    def roll(self) -> None:
        if not self.game.player.bets:
            self.msg_var.set("Bạn chưa đặt cược! Bấm vào linh vật trước.")
            return
        self.set_enabled(False)
        self.animate(0)

    def animate(self, frame: int) -> None:
        MAX_FRAMES = 50
        DELAY_MS = 80
        
        if frame < MAX_FRAMES:
            for lbl in self.dice_labels:
                lbl.config(text=random.choice(list(Symbol)).icon)
            self.root.after(DELAY_MS, self.animate, frame + 1)
        else:
            self.finish_roll()

    def finish_roll(self) -> None:
        outcome = self.game.play_round()
        self.last_bets = outcome.bets
        for lbl, symbol in zip(self.dice_labels, outcome.dice):
            lbl.config(text=symbol.icon)
        if outcome.net > 0:
            self.msg_var.set(f"🎉 Bạn thắng +{outcome.net} chip! Đặt cược lượt mới.")
        elif outcome.net < 0:
            self.msg_var.set(f"😢 Bạn thua {outcome.net} chip. Đặt cược lượt mới.")
        else:
            self.msg_var.set("😐 Hòa vốn. Đặt cược lượt mới.")
        self.refresh()
        self.set_enabled(True)
        if self.game.player.chips < 10:
            self.game_over()

    def game_over(self) -> None:
        if messagebox.askyesno("Hết tiền", "Bạn đã hết chip!\nChơi lại từ đầu?"):
            self.game.restart()
            self.msg_var.set("Ván mới! Chọn mức cược rồi đặt.")
            self.refresh()
        else:
            self.root.destroy()


def run_gui(game: Game) -> None:
    root = tk.Tk()
    App(root, game)
    root.mainloop()
