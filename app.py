"""将在线论文阅读器逐页截图并合成为 PDF 的 macOS 桌面应用。"""

from __future__ import annotations

import queue
import re
import shutil
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

import img2pdf
import pyautogui


class ScreenshotBookApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("论文截图合并工具")
        self.resizable(False, False)
        self.coords: dict[str, tuple[int, int]] = {}
        self.messages: queue.Queue[tuple[str, str]] = queue.Queue()
        self.running = False

        self.pages = tk.StringVar(value="385")
        self.book_name = tk.StringVar(value="论文")
        self.status = tk.StringVar(value="请先填写页数和书名，再依次记录三个位置。")
        self._build_ui()
        self.after(100, self._receive_messages)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=20)
        frame.grid(sticky="nsew")

        ttk.Label(frame, text="论文截图合并工具", font=("Helvetica", 18, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 12)
        )
        ttk.Label(frame, text="总页数：").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.pages, width=18).grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(frame, text="书名（生成的 PDF 文件名）：").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.book_name, width=30).grid(row=2, column=1, columnspan=2, sticky="we", pady=4)

        ttk.Separator(frame).grid(row=3, column=0, columnspan=3, sticky="we", pady=12)
        ttk.Label(frame, text="按顺序记录位置。点击按钮后有 3 秒可将鼠标移到目标处。", wraplength=450).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )
        self.coord_labels: dict[str, ttk.Label] = {}
        locations = [
            ("arrow", "1. 下一页箭头", "把鼠标放在 PDF 阅读器的下一页按钮上"),
            ("top_left", "2. 正文左上角", "把鼠标放在需要截取的正文区域左上角"),
            ("bottom_right", "3. 正文右下角", "把鼠标放在需要截取的正文区域右下角"),
        ]
        for row, (key, label, instruction) in enumerate(locations, start=5):
            ttk.Button(frame, text="记录", command=lambda k=key, i=instruction: self._record_position(k, i)).grid(
                row=row, column=0, sticky="w", pady=4
            )
            ttk.Label(frame, text=label).grid(row=row, column=1, sticky="w", padx=(8, 8))
            result = ttk.Label(frame, text="未记录", foreground="#666666")
            result.grid(row=row, column=2, sticky="w")
            self.coord_labels[key] = result

        ttk.Separator(frame).grid(row=8, column=0, columnspan=3, sticky="we", pady=12)
        self.start_button = ttk.Button(frame, text="开始截图并生成 PDF", command=self._start)
        self.start_button.grid(row=9, column=0, columnspan=3, sticky="we", ipady=5)
        ttk.Label(frame, textvariable=self.status, foreground="#285a9f", wraplength=450).grid(
            row=10, column=0, columnspan=3, sticky="w", pady=(12, 0)
        )
        ttk.Label(
            frame,
            text="提示：首次运行请在 macOS「系统设置 > 隐私与安全性」中允许屏幕录制和辅助功能权限。",
            foreground="#666666",
            wraplength=450,
        ).grid(row=11, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def _record_position(self, key: str, instruction: str) -> None:
        if self.running:
            return
        self.status.set(f"{instruction}，3 秒后自动记录…")
        self.update_idletasks()
        self.after(3000, lambda: self._save_position(key))

    def _save_position(self, key: str) -> None:
        position = pyautogui.position()
        self.coords[key] = (position.x, position.y)
        self.coord_labels[key].configure(text=f"({position.x}, {position.y})", foreground="#167a34")
        self.status.set("位置已记录。")

    def _start(self) -> None:
        try:
            total_pages = int(self.pages.get())
            if total_pages < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("页数无效", "总页数必须是大于 0 的整数。")
            return
        if set(self.coords) != {"arrow", "top_left", "bottom_right"}:
            messagebox.showerror("缺少位置", "请先记录下一页箭头、正文左上角和正文右下角。")
            return
        name = self._safe_filename(self.book_name.get())
        if not name:
            messagebox.showerror("书名无效", "请填写书名。")
            return
        x1, y1 = self.coords["top_left"]
        x2, y2 = self.coords["bottom_right"]
        if x2 <= x1 or y2 <= y1:
            messagebox.showerror("截图区域无效", "右下角必须在左上角的右下方，请重新记录。")
            return
        self.running = True
        self.start_button.configure(state="disabled")
        threading.Thread(target=self._capture, args=(total_pages, name), daemon=True).start()

    @staticmethod
    def _safe_filename(name: str) -> str:
        cleaned = re.sub(r'[\\/:*?"<>|]', "_", name).strip().rstrip(".")
        return cleaned[:-4] if cleaned.lower().endswith(".pdf") else cleaned

    def _capture(self, total_pages: int, name: str) -> None:
        output_dir = Path.home() / "Desktop" / "论文截图工具输出"
        work_dir = output_dir / "临时截图"
        output_pdf = output_dir / f"{name}.pdf"
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            shutil.rmtree(work_dir, ignore_errors=True)
            work_dir.mkdir()
            arrow_x, arrow_y = self.coords["arrow"]
            x1, y1 = self.coords["top_left"]
            x2, y2 = self.coords["bottom_right"]
            width, height = x2 - x1, y2 - y1
            for left in range(5, 0, -1):
                self.messages.put(("status", f"请在 {left} 秒内切回浏览器并保持 PDF 阅读器在前台…"))
                time.sleep(1)
            images: list[str] = []
            for page in range(1, total_pages + 1):
                self.messages.put(("status", f"正在处理第 {page}/{total_pages} 页…"))
                image_path = work_dir / f"page_{page:04d}.png"
                pyautogui.screenshot(region=(x1, y1, width, height)).save(image_path)
                images.append(str(image_path))
                if page < total_pages:
                    pyautogui.click(arrow_x, arrow_y)
                    time.sleep(0.8)
            self.messages.put(("status", "正在合并为 PDF…"))
            with output_pdf.open("wb") as pdf_file:
                pdf_file.write(img2pdf.convert(images))
            shutil.rmtree(work_dir, ignore_errors=True)
            self.messages.put(("done", f"完成！PDF 已保存到：\n{output_pdf}"))
        except Exception as exc:
            self.messages.put(("error", f"处理失败：{exc}"))

    def _receive_messages(self) -> None:
        try:
            while True:
                kind, content = self.messages.get_nowait()
                self.status.set(content)
                if kind == "done":
                    self.running = False
                    self.start_button.configure(state="normal")
                    messagebox.showinfo("完成", content)
                elif kind == "error":
                    self.running = False
                    self.start_button.configure(state="normal")
                    messagebox.showerror("处理失败", content)
        except queue.Empty:
            pass
        self.after(100, self._receive_messages)


if __name__ == "__main__":
    ScreenshotBookApp().mainloop()

