import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import main
from utils import Config

class VideoSummaryGUI:
    """Bilibili/YouTube 字幕获取与总结工具GUI界面"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Bilibili/YouTube 视频字幕获取与总结工具")
        self.root.geometry("800x600")
        
        # 创建配置
        self.config = Config()
        
        # 创建界面
        self.create_widgets()
        self._sync_ui_state()
    
    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # URL输入区域
        url_frame = ttk.LabelFrame(main_frame, text="视频URL（Bilibili/YouTube）", padding="10")
        url_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.url_entry = ttk.Entry(url_frame, width=70)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.url_entry.insert(0, "https://www.bilibili.com/video/BV1RLqdBgEPN/")
        
        # 选项区域
        options_frame = ttk.LabelFrame(main_frame, text="选项", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 第一行选项
        row1_frame = ttk.Frame(options_frame)
        row1_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.no_summary_var = tk.BooleanVar()
        self.no_summary_check = ttk.Checkbutton(
            row1_frame, text="不生成总结（仅导出字幕）", variable=self.no_summary_var,
            command=self._sync_ui_state
        )
        self.no_summary_check.pack(side=tk.LEFT)
        
        self.json_var = tk.BooleanVar()
        self.json_check = ttk.Checkbutton(
            row1_frame, text="保存为JSON格式", variable=self.json_var,
            command=self._sync_ui_state
        )
        self.json_check.pack(side=tk.LEFT, padx=(20, 0))
        
        self.verbose_var = tk.BooleanVar()
        self.verbose_check = ttk.Checkbutton(
            row1_frame, text="详细输出", variable=self.verbose_var
        )
        self.verbose_check.pack(side=tk.LEFT, padx=(20, 0))
        
        # 第二行选项
        row2_frame = ttk.Frame(options_frame)
        row2_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(row2_frame, text="API Key:").pack(side=tk.LEFT)
        self.api_key_entry = ttk.Entry(row2_frame, width=24, show="*")
        self.api_key_entry.pack(side=tk.LEFT, padx=(5, 10))
        self.api_key_entry.insert(0, self.config.AI_API_KEY)

        ttk.Label(row2_frame, text="API地址:").pack(side=tk.LEFT)
        self.api_base_url_entry = ttk.Entry(row2_frame, width=36)
        self.api_base_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.api_base_url_entry.insert(0, self.config.AI_BASE_URL)

        # 第三行选项
        row3_frame = ttk.Frame(options_frame)
        row3_frame.pack(fill=tk.X)
        
        ttk.Label(row3_frame, text="AI模型:").pack(side=tk.LEFT)
        self.model_entry = ttk.Entry(row3_frame, width=20)
        self.model_entry.pack(side=tk.LEFT, padx=(5, 0))
        self.model_entry.insert(0, self.config.DEFAULT_MODEL)

        ttk.Label(row3_frame, text="字幕格式:").pack(side=tk.LEFT, padx=(20, 5))
        self.subtitle_format_var = tk.StringVar(value="srt")
        self.subtitle_format_combo = ttk.Combobox(
            row3_frame,
            textvariable=self.subtitle_format_var,
            values=["srt"],
            width=8,
            state="readonly"
        )
        self.subtitle_format_combo.pack(side=tk.LEFT)
        self.subtitle_format_combo.bind("<<ComboboxSelected>>", lambda _e: self._sync_ui_state())
        
        ttk.Label(row3_frame, text="输出路径:").pack(side=tk.LEFT, padx=(20, 5))
        self.output_entry = ttk.Entry(row3_frame, width=30)
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.output_entry.insert(0, "output")
        
        self.browse_button = ttk.Button(
            row3_frame, text="浏览", command=self.browse_output_file
        )
        self.browse_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        # 操作按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.process_button = ttk.Button(
            button_frame, text="开始处理", command=self.start_processing
        )
        self.process_button.pack(side=tk.LEFT)
        
        self.clear_button = ttk.Button(
            button_frame, text="清空", command=self.clear_fields
        )
        self.clear_button.pack(side=tk.LEFT, padx=(10, 0))
        
        self.example_button = ttk.Button(
            button_frame, text="Bilibili示例", command=self.load_example
        )
        self.example_button.pack(side=tk.LEFT, padx=(10, 0))
        
        # 输出区域
        output_frame = ttk.LabelFrame(main_frame, text="输出", padding="10")
        output_frame.pack(fill=tk.BOTH, expand=True)
        
        self.output_text = scrolledtext.ScrolledText(
            output_frame, wrap=tk.WORD, width=80, height=15
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)

        hint = ttk.Label(
            output_frame,
            text="提示：非JSON字幕导出会自动生成同名 .md 便于阅读",
            foreground="#666666"
        )
        hint.pack(anchor="w", pady=(6, 0))
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))
    
    def browse_output_file(self):
        """选择输出文件"""
        if self.json_var.get():
            file_types = [("JSON文件", "*.json"), ("所有文件", "*.*")]
            default_extension = ".json"
        elif self.no_summary_var.get():
            fmt = self.subtitle_format_var.get().strip() or "srt"
            file_types = [(f"{fmt.upper()} 文件", f"*.{fmt}"), ("所有文件", "*.*")]
            default_extension = f".{fmt}"
        else:
            file_types = [("Markdown文件", "*.md"), ("文本文件", "*.txt"), ("所有文件", "*.*")]
            default_extension = ".md"
        
        file_path = filedialog.asksaveasfilename(
            title="选择输出文件",
            filetypes=file_types,
            defaultextension=default_extension
        )
        
        if file_path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, file_path)
    
    def load_example(self):
        """加载Bilibili示例URL"""
        example_url = "https://www.bilibili.com/video/BV1RLqdBgEPN/"
        self.url_entry.delete(0, tk.END)
        self.url_entry.insert(0, example_url)
    
    def clear_fields(self):
        """清空输入字段"""
        self.url_entry.delete(0, tk.END)
        self.output_entry.delete(0, tk.END)
        self.output_text.delete(1.0, tk.END)
        self.api_key_entry.delete(0, tk.END)
        self.api_key_entry.insert(0, self.config.AI_API_KEY)
        self.api_base_url_entry.delete(0, tk.END)
        self.api_base_url_entry.insert(0, self.config.AI_BASE_URL)
        self.model_entry.delete(0, tk.END)
        self.model_entry.insert(0, self.config.DEFAULT_MODEL)
        self.output_entry.insert(0, "output")
        self.no_summary_var.set(False)
        self.json_var.set(False)
        self.subtitle_format_var.set("srt")
        self.verbose_var.set(False)
        self._sync_ui_state()

    def _sync_ui_state(self):
        """根据当前选项同步控件状态"""
        no_summary = self.no_summary_var.get()
        is_json = self.json_var.get()

        self.api_key_entry.config(state=tk.DISABLED if no_summary else tk.NORMAL)
        self.api_base_url_entry.config(state=tk.DISABLED if no_summary else tk.NORMAL)
        self.model_entry.config(state=tk.DISABLED if no_summary else tk.NORMAL)
        self.subtitle_format_combo.config(state="readonly" if no_summary and not is_json else tk.DISABLED)
    
    def start_processing(self):
        """开始处理视频"""
        # 获取输入值
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入 Bilibili 或 YouTube 视频URL")
            return
        
        # 构建命令行参数
        try:
            # 构建新的sys.argv
            argv = ["main.py", "-u", url]
            
            output_value = self.output_entry.get().strip()
            # 默认 output 目录不传 -o，让主流程按默认命名写入 output/
            if output_value and output_value.lower() not in {"output", "output/", "output\\"}:
                argv.extend(["-o", output_value])
            
            if not self.no_summary_var.get() and self.model_entry.get().strip():
                argv.extend(["-m", self.model_entry.get().strip()])
            
            if self.no_summary_var.get():
                argv.append("--no-summary")
            
            if self.json_var.get():
                argv.append("--json")
            elif self.no_summary_var.get():
                argv.extend(["--subtitle-format", self.subtitle_format_var.get().strip() or "srt"])
            
            if self.verbose_var.get():
                argv.append("-v")
            
            # 在新线程中处理，避免阻塞GUI
            self.process_button.config(state=tk.DISABLED)
            self.status_var.set("处理中...")
            
            processing_thread = threading.Thread(target=self.process_video, args=(argv,))
            processing_thread.daemon = True
            processing_thread.start()
            
        except Exception as e:
            messagebox.showerror("错误", f"启动处理失败: {e}")
            self.process_button.config(state=tk.NORMAL)
            self.status_var.set("就绪")
    
    def process_video(self, argv):
        """处理视频（在新线程中运行）"""
        try:
            # 重定向输出到GUI
            from io import StringIO
            old_stdout = sys.stdout
            old_argv = sys.argv
            old_env_api_key = os.environ.get("AI_API_KEY")
            old_env_base_url = os.environ.get("AI_BASE_URL")
            sys.stdout = StringIO()
            sys.argv = argv
            input_api_key = self.api_key_entry.get().strip()
            input_base_url = self.api_base_url_entry.get().strip()

            # GUI留空时不覆盖现有环境变量，避免把 .env 中的值清空
            if input_api_key:
                os.environ["AI_API_KEY"] = input_api_key
            elif old_env_api_key is None:
                os.environ.pop("AI_API_KEY", None)

            os.environ["AI_BASE_URL"] = input_base_url or self.config.AI_BASE_URL
            
            try:
                main()
                output = sys.stdout.getvalue()
                
                # 在主线程中更新GUI
                self.root.after(0, self.update_gui_output, output, True)
                
            finally:
                sys.stdout = old_stdout
                sys.argv = old_argv
                if old_env_api_key is None:
                    os.environ.pop("AI_API_KEY", None)
                else:
                    os.environ["AI_API_KEY"] = old_env_api_key
                if old_env_base_url is None:
                    os.environ.pop("AI_BASE_URL", None)
                else:
                    os.environ["AI_BASE_URL"] = old_env_base_url
                
        except SystemExit as e:
            # 处理main()中的sys.exit()
            if e.code == 0:
                self.root.after(0, self.update_gui_output, "处理完成!", True)
            else:
                self.root.after(0, self.update_gui_output, f"处理失败，退出码: {e.code}", False)
                
        except Exception as e:
            self.root.after(0, self.update_gui_output, f"处理失败: {e}", False)
    
    def update_gui_output(self, message, success):
        """更新GUI输出（在主线程中调用）"""
        self.output_text.delete(1.0, tk.END)
        self.output_text.insert(tk.END, message)
        
        if success:
            self.status_var.set("处理完成")
        else:
            self.status_var.set("处理失败")
        
        self.process_button.config(state=tk.NORMAL)

def main_gui():
    """启动GUI"""
    root = tk.Tk()
    app = VideoSummaryGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main_gui()