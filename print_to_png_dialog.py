from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class SaveOptions:
    target_path: Path
    dpi: int
    create_folder: bool
    create_zip: bool


def prompt_png_save_dialog(
    default_filename: str,
    initial_dir: str,
    default_dpi: int,
    page_count: int,
) -> Optional[SaveOptions]:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    result: list[SaveOptions] = []
    root = tk.Tk()
    root.title("Print to PNG - 輸出設定")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    filename_var = tk.StringVar(value=f"{default_filename}.png")
    folder_var = tk.StringVar(value=initial_dir)
    dpi_var = tk.StringVar(value=str(default_dpi))
    create_folder_var = tk.BooleanVar(value=page_count > 1)
    create_zip_var = tk.BooleanVar(value=False)

    frame = ttk.Frame(root, padding=16)
    frame.grid()
    frame.columnconfigure(1, weight=1)

    ttk.Label(frame, text="檔案名稱:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(frame, textvariable=filename_var, width=48).grid(
        row=0, column=1, columnspan=2, sticky="ew", pady=4
    )
    ttk.Label(frame, text="輸出資料夾:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(frame, textvariable=folder_var, width=48).grid(
        row=1, column=1, sticky="ew", pady=4
    )

    def browse_folder() -> None:
        selected = filedialog.askdirectory(
            parent=root, initialdir=folder_var.get(), title="選擇 PNG 輸出資料夾"
        )
        if selected:
            folder_var.set(selected)

    ttk.Button(frame, text="瀏覽...", command=browse_folder).grid(
        row=1, column=2, padx=(8, 0), pady=4
    )
    ttk.Label(frame, text="DPI:").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(frame, textvariable=dpi_var, width=12).grid(row=2, column=1, sticky="w", pady=4)
    ttk.Label(frame, text="允許範圍：72–4800").grid(row=2, column=1, sticky="w", padx=(110, 0))

    ttk.Checkbutton(
        frame, text="建立同名資料夾", variable=create_folder_var
    ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(12, 2))
    ttk.Checkbutton(
        frame, text="同時建立 ZIP", variable=create_zip_var
    ).grid(row=4, column=0, columnspan=3, sticky="w", pady=2)
    ttk.Label(
        frame,
        text=f"本次列印共 {page_count} 頁；PNG 將依頁數自動命名。",
    ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 4))

    button_frame = ttk.Frame(frame)
    button_frame.grid(row=6, column=0, columnspan=3, sticky="e", pady=(12, 0))

    def save() -> None:
        filename = filename_var.get().strip()
        if not filename:
            messagebox.showerror("輸入錯誤", "請輸入檔案名稱。", parent=root)
            return
        if not filename.lower().endswith(".png"):
            filename += ".png"
        try:
            dpi = int(dpi_var.get().strip())
        except ValueError:
            messagebox.showerror("輸入錯誤", "DPI 必須是整數。", parent=root)
            return
        if not 72 <= dpi <= 4800:
            messagebox.showerror("輸入錯誤", "DPI 必須介於 72 到 4800。", parent=root)
            return
        folder = Path(folder_var.get().strip()).expanduser()
        if not folder.exists() or not folder.is_dir():
            messagebox.showerror("輸入錯誤", "輸出資料夾不存在。", parent=root)
            return
        result.append(
            SaveOptions(
                target_path=folder / filename,
                dpi=dpi,
                create_folder=create_folder_var.get(),
                create_zip=create_zip_var.get(),
            )
        )
        root.destroy()

    ttk.Button(button_frame, text="儲存", command=save).grid(row=0, column=0, padx=4)
    ttk.Button(button_frame, text="取消", command=root.destroy).grid(row=0, column=1, padx=4)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
    return result[0] if result else None
