import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import sys
import os
import re

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import main
from utils import Config
from video_summarizer import VideoSummarizer

class VideoSummaryGUI:
    """Bilibili/YouTube 字幕获取与总结工具GUI界面"""
    MODEL_CANDIDATES = ["GLM-4.7", "GLM-5", "GLM-4.7-FlashX"]
    
    def __init__(self, root):
        self.root = root
        self.root.title("Bilibili/YouTube 视频字幕获取与总结工具")
        self.root.geometry("800x600")
        
        # 创建配置
        self.config = Config()
        self.chat_history = []
        self.loaded_summary_path = None
        
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
        options_frame = ttk.LabelFrame(main_frame, text="如无apikey，选择获取字幕，另行导入知识工具", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 第一行选项
        row1_frame = ttk.Frame(options_frame)
        row1_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.mode_var = tk.StringVar(value="summary")
        self.subtitle_mode_radio = ttk.Radiobutton(
            row1_frame, text="获取字幕", variable=self.mode_var, value="subtitle",
            command=self._sync_ui_state
        )
        self.subtitle_mode_radio.pack(side=tk.LEFT)
        self.summary_mode_radio = ttk.Radiobutton(
            row1_frame, text="自动总结", variable=self.mode_var, value="summary",
            command=self._sync_ui_state
        )
        self.summary_mode_radio.pack(side=tk.LEFT, padx=(20, 0))
        
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
        self.model_var = tk.StringVar(value=self.config.DEFAULT_MODEL)
        self.model_entry = ttk.Combobox(
            row3_frame,
            textvariable=self.model_var,
            values=self.MODEL_CANDIDATES,
            width=20,
            state="normal"  # 允许手动输入自定义模型
        )
        self.model_entry.pack(side=tk.LEFT, padx=(5, 0))

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
            text="提示：字幕模式会同时导出 .srt 和同名 .md；总结模式导出 .md;文件保存在output，可以使用其他知识管理工具检索",
            foreground="#666666"
        )
        hint.pack(anchor="w", pady=(6, 0))

        # 对话区域
        chat_frame = ttk.LabelFrame(main_frame, text="和大模型对话", padding="10")
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.chat_text = scrolledtext.ScrolledText(
            chat_frame, wrap=tk.WORD, width=80, height=8
        )
        self.chat_text.pack(fill=tk.BOTH, expand=True)
        self.chat_text.insert(tk.END, "你可以直接输入问题并点击“发送”。\n")

        chat_input_frame = ttk.Frame(chat_frame)
        chat_input_frame.pack(fill=tk.X, pady=(8, 0))

        self.chat_input = tk.Text(chat_input_frame, height=3, wrap=tk.WORD)
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.chat_input.bind("<Return>", self._on_chat_enter)
        self.chat_input.bind("<Shift-Return>", self._on_chat_shift_enter)

        self.send_button = ttk.Button(
            chat_input_frame, text="发送", command=self.send_chat_message
        )
        self.send_button.pack(side=tk.LEFT, padx=(8, 0))
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))
    
    def browse_output_file(self):
        """选择输出文件"""
        if self.mode_var.get() == "subtitle":
            file_types = [("SRT文件", "*.srt"), ("所有文件", "*.*")]
            default_extension = ".srt"
        else:
            file_types = [("Markdown文件", "*.md"), ("所有文件", "*.*")]
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
        """仅清空对话与输出内容，保留参数便于重试"""
        self.output_text.delete(1.0, tk.END)
        self.chat_text.delete(1.0, tk.END)
        self.chat_text.insert(tk.END, "你可以直接输入问题并点击“发送”。\n")
        self.chat_input.delete("1.0", tk.END)
        self.chat_history = []
        self.loaded_summary_path = None
        self.status_var.set("就绪")
        self._sync_ui_state()

    def _sync_ui_state(self):
        """根据当前选项同步控件状态"""
        # API配置同时服务于“自动总结”和“对话”，因此始终可编辑
        self.api_key_entry.config(state=tk.NORMAL)
        self.api_base_url_entry.config(state=tk.NORMAL)
        self.model_entry.config(state=tk.NORMAL)
    
    def start_processing(self):
        """开始处理视频"""
        # 获取输入值
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入 Bilibili 或 YouTube 视频URL")
            return
        need_summary = self.mode_var.get() == "summary"
        if need_summary and not self.api_key_entry.get().strip():
            messagebox.showerror("错误", "需要生成总结时，API Key 不能为空")
            return
        
        # 构建命令行参数
        try:
            # 构建新的sys.argv
            argv = ["main.py", "-u", url]
            
            output_value = self.output_entry.get().strip()
            # 默认 output 目录不传 -o，让主流程按默认命名写入 output/
            if output_value and output_value.lower() not in {"output", "output/", "output\\"}:
                argv.extend(["-o", output_value])
            
            if need_summary and self.model_entry.get().strip():
                argv.extend(["-m", self.model_entry.get().strip()])

            if need_summary:
                api_key = self.api_key_entry.get().strip()
                api_base_url = self.api_base_url_entry.get().strip()
                argv.extend(["--api-key", api_key])
                if api_base_url:
                    argv.extend(["--api-base-url", api_base_url])
            
            if self.mode_var.get() == "subtitle":
                argv.append("--no-summary")
            
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
            output_buffer = StringIO()
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            old_argv = sys.argv
            sys.stdout = output_buffer
            sys.stderr = output_buffer
            sys.argv = argv
            
            try:
                main()
                output = output_buffer.getvalue()
                
                # 在主线程中更新GUI
                self.root.after(0, self.update_gui_output, output, True)
                
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                sys.argv = old_argv
                
        except SystemExit as e:
            # 处理main()中的sys.exit()
            output = ""
            try:
                output = output_buffer.getvalue().strip()
            except Exception:
                output = ""
            if e.code == 0:
                message = output if output else "处理完成!"
                self.root.after(0, self.update_gui_output, message, True)
            else:
                if output:
                    message = f"{output}\n\n处理失败，退出码: {e.code}"
                else:
                    message = f"处理失败，退出码: {e.code}"
                self.root.after(0, self.update_gui_output, message, False)
                
        except Exception as e:
            self.root.after(0, self.update_gui_output, f"处理失败: {e}", False)

    def _on_chat_enter(self, _event):
        """回车发送聊天消息"""
        self.send_chat_message()
        return "break"

    def _on_chat_shift_enter(self, event):
        """Shift+Enter 插入换行"""
        event.widget.insert(tk.INSERT, "\n")
        return "break"

    def _build_runtime_config(self):
        """根据GUI输入构建运行时配置"""
        runtime_config = Config()
        runtime_config.AI_API_KEY = self.api_key_entry.get().strip()
        base_url = self.api_base_url_entry.get().strip()
        if base_url:
            runtime_config.AI_BASE_URL = base_url
        return runtime_config

    def send_chat_message(self):
        """发送聊天消息"""
        user_message = self.chat_input.get("1.0", tk.END).strip()
        if not user_message:
            messagebox.showerror("错误", "请输入聊天内容")
            return

        if not self.api_key_entry.get().strip():
            messagebox.showerror("错误", "请先填写 API Key")
            return

        self.chat_input.delete("1.0", tk.END)
        self.append_chat_message("你", user_message)
        history_snapshot = list(self.chat_history)
        self.chat_history.append({"role": "user", "content": user_message})
        self.send_button.config(state=tk.DISABLED)
        self.status_var.set("对话中...")

        chat_thread = threading.Thread(target=self.chat_with_model, args=(user_message, history_snapshot))
        chat_thread.daemon = True
        chat_thread.start()

    def chat_with_model(self, user_message, history_snapshot):
        """后台线程：调用大模型聊天"""
        try:
            runtime_config = self._build_runtime_config()
            summarizer = VideoSummarizer(runtime_config)
            model_name = self.model_entry.get().strip() or None
            reply = summarizer.chat(user_message, model=model_name, history=history_snapshot)
            if reply:
                self.root.after(0, self.append_chat_message, "AI", reply)
                self.chat_history.append({"role": "assistant", "content": reply})
                self.root.after(0, self.status_var.set, "就绪")
            else:
                self.root.after(0, self.append_chat_message, "AI", "未收到有效回复，请检查配置或重试。")
                self.root.after(0, self.status_var.set, "对话失败")
        except Exception as e:
            self.root.after(0, self.append_chat_message, "系统", f"对话失败: {e}")
            self.root.after(0, self.status_var.set, "对话失败")
        finally:
            self.root.after(0, self.send_button.config, {"state": tk.NORMAL})

    def append_chat_message(self, role, message):
        """向对话区追加消息"""
        self.chat_text.insert(tk.END, f"\n[{role}] {message}\n")
        self.chat_text.see(tk.END)
    
    def update_gui_output(self, message, success):
        """更新GUI输出（在主线程中调用）"""
        self.output_text.delete(1.0, tk.END)
        self.output_text.insert(tk.END, message)
        
        if success:
            self.status_var.set("处理完成")
            self.try_load_summary_context(message)
        else:
            self.status_var.set("处理失败")
        
        self.process_button.config(state=tk.NORMAL)

    def try_load_summary_context(self, output_message):
        """从处理输出中识别总结文件并加载到对话历史"""
        if not output_message:
            return
        matches = re.findall(r"总结已保存到:\s*(.+)", output_message)
        if not matches:
            return

        summary_path = matches[-1].strip()
        if not summary_path:
            return

        summary_path = os.path.normpath(summary_path)
        if not os.path.isabs(summary_path):
            summary_path = os.path.normpath(os.path.join(os.getcwd(), summary_path))
        if not os.path.exists(summary_path):
            return
        if self.loaded_summary_path == summary_path:
            return

        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                summary_content = f.read().strip()
            if not summary_content:
                return
            self.chat_history = [{
                "role": "system",
                "content": (
                    "以下是刚生成的视频总结，请基于这份总结持续对话。"
                    "若用户问题超出总结范围，请明确说明并给出可执行建议。\n\n"
                    f"{summary_content}"
                )
            }]
            self.loaded_summary_path = summary_path
            self.append_chat_message("系统", f"总结上下文加载完毕：{summary_path}\n现在可以直接继续对话。")
        except Exception as e:
            self.append_chat_message("系统", f"总结上下文加载失败: {e}")

def main_gui():
    """启动GUI"""
    root = tk.Tk()
    app = VideoSummaryGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main_gui()