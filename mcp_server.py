"""
videosummary MCP Server

把视频字幕提取、AI 总结、对话能力，以及个人游戏编程能力框架文档，
封装成 MCP 工具和资源，让 Cursor 通过 stdio 协议直接调用。

运行方式：
    python mcp_server.py
"""

import os
import re
import sys
from datetime import date
from pathlib import Path

# 确保本目录在 sys.path 里（不论从哪个 cwd 启动）
_HERE = Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# 切换工作目录，保证 .env、key.json 等相对路径能被 Config 正确解析
os.chdir(_HERE)

from mcp.server.fastmcp import FastMCP
from subtitle_extractor import SubtitleExtractor
from video_summarizer import VideoSummarizer
from utils import Config

# ── 初始化 ──────────────────────────────────────────────────────────────────
mcp = FastMCP(
    "videosummary",
    instructions=(
        "视频字幕与总结工具。"
        "支持 Bilibili / YouTube 字幕提取、AI 摘要生成、大模型对话，"
        "以及读取个人游戏编程能力框架文档。"
    ),
)

_config = Config()
_extractor = SubtitleExtractor(_config)
_summarizer = VideoSummarizer(_config)

_FRAMEWORK_PATH = _HERE / "GAME_PROGRAMMING_SKILL_FRAMEWORK.md"


# ── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_subtitle(url: str) -> str:
    """提取 Bilibili 或 YouTube 视频字幕，保存到 output/{日期}/ 目录，返回文件路径。

    参数:
        url: 视频链接，支持 Bilibili BV/av 号、YouTube watch?v= 和 shorts。

    返回:
        保存结果（文件路径 + 视频基本信息），不返回字幕正文。
    """
    subtitle_data = _extractor.extract_subtitles(url, subtitle_format="srt")
    if not subtitle_data:
        return "字幕提取失败：该视频无可用字幕，或平台暂不支持。"

    video_info = subtitle_data.get("video_info", {})
    title = video_info.get("title", "未知标题")
    owner = video_info.get("owner", "")
    duration = video_info.get("duration", 0)
    platform = subtitle_data.get("platform", "")

    subtitles = subtitle_data.get("subtitles", [])
    if not subtitles:
        return "字幕提取失败：字幕数据为空。"

    # 按日期建子目录
    today = date.today().strftime("%Y-%m-%d")
    out_dir = _HERE / _config.OUTPUT_DIR / today
    out_dir.mkdir(parents=True, exist_ok=True)

    # 视频 ID（BV号 / YouTube ID）
    vid_id = _extract_vid_id(url)

    # 标题前 8 个合法字符（保留汉字、字母、数字、短横线和下划线）
    title_prefix = re.sub(r"[^\w\u4e00-\u9fff-]", "", title)[:8]

    stem = f"{title_prefix}_{vid_id}" if title_prefix else vid_id
    srt_path = str(out_dir / f"{stem}_subtitles.srt")
    md_path  = str(out_dir / f"{stem}_subtitles.md")

    _extractor.save_subtitles_to_file(subtitle_data, srt_path)
    _extractor.save_subtitles_to_markdown(subtitle_data, md_path)

    mins, secs = divmod(int(duration), 60)
    return (
        f"字幕已保存\n"
        f"标题：{title}\n"
        f"平台：{platform}  UP主/作者：{owner}  时长：{mins}:{secs:02d}\n"
        f"SRT: {srt_path}\n"
        f"MD:  {md_path}"
    )


@mcp.tool()
def summarize_video(url: str, model: str = "") -> str:
    """提取视频字幕并调用大模型生成结构化 Markdown 总结。

    参数:
        url:   视频链接，支持 Bilibili / YouTube。
        model: 可选，指定模型名称（如 GLM-4.7）；留空使用 .env 中 DEFAULT_MODEL。

    返回:
        Markdown 格式的视频总结，包含主要内容、关键点和标签；或失败原因。
    """
    subtitle_data = _extractor.extract_subtitles(url, subtitle_format="srt")
    if not subtitle_data:
        return "字幕提取失败：该视频无可用字幕，或平台暂不支持。"

    result = _summarizer.summarize_video(
        subtitle_data, model=model if model.strip() else None
    )
    if not result:
        return (
            "总结生成失败：请检查 .env 中的 AI_API_KEY / AI_BASE_URL / DEFAULT_MODEL 配置。"
        )

    video_info = subtitle_data.get("video_info", {})
    title = video_info.get("title", "未知标题")
    return f"# {title}\n\n{result}"


@mcp.tool()
def chat(message: str, model: str = "") -> str:
    """与 .env 中配置的大模型直接对话。

    参数:
        message: 发送给模型的消息内容。
        model:   可选，指定模型名称；留空使用 .env 中 DEFAULT_MODEL。

    返回:
        模型回复的文本；或失败原因。
    """
    if not message.strip():
        return "消息内容不能为空。"

    result = _summarizer.chat(
        message, model=model if model.strip() else None
    )
    return result or "对话失败：请检查 AI_API_KEY / AI_BASE_URL 配置。"


# ── Resources ────────────────────────────────────────────────────────────────

@mcp.resource("game-framework://skill-framework")
def skill_framework() -> str:
    """返回个人游戏编程能力框架文档（GAME_PROGRAMMING_SKILL_FRAMEWORK.md）全文。

    用途：在 Cursor 对话中随时引用自己的技能框架，辅助规划学习任务、制定周计划。
    """
    if not _FRAMEWORK_PATH.exists():
        return "框架文档不存在，请先创建 GAME_PROGRAMMING_SKILL_FRAMEWORK.md。"
    return _FRAMEWORK_PATH.read_text(encoding="utf-8")


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _fmt_ts(seconds: float) -> str:
    """将秒数格式化为 HH:MM:SS"""
    total = max(0, int(seconds))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _extract_vid_id(url: str) -> str:
    """从 URL 提取稳定视频 ID（BV号 / YouTube ID），取不到时回退到 'video'"""
    bv = re.search(r"(BV[a-zA-Z0-9]+)", url)
    if bv:
        return bv.group(1)
    yt = re.search(r"[?&]v=([a-zA-Z0-9_-]{6,})", url)
    if yt:
        return yt.group(1)
    short = re.search(r"youtu\.be/([a-zA-Z0-9_-]{6,})", url)
    if short:
        return short.group(1)
    return "video"


# ── 入口 ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
