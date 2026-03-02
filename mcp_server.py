"""
videosummary MCP Server

把视频字幕提取、AI 总结、对话能力，以及个人游戏编程能力框架文档，
封装成 MCP 工具和资源，让 Cursor 通过 stdio 协议直接调用。

运行方式：
    python mcp_server.py
"""

import os
import sys
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
    """提取 Bilibili 或 YouTube 视频的字幕，返回带时间戳的纯文本。

    参数:
        url: 视频链接，支持 Bilibili BV/av 号、YouTube watch?v= 和 shorts。

    返回:
        字幕文本（Markdown 格式，含视频标题和时间戳行），或失败原因。
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

    body = subtitles[0].get("body", [])
    lines = []
    for item in body:
        start = _fmt_ts(item.get("from", 0))
        end = _fmt_ts(item.get("to", 0))
        content = item.get("content", "")
        if content:
            lines.append(f"[{start} - {end}] {content}")

    mins, secs = divmod(int(duration), 60)
    header = (
        f"# {title}\n\n"
        f"- 平台：{platform}\n"
        f"- UP主/作者：{owner}\n"
        f"- 时长：{mins}:{secs:02d}\n\n"
        f"## 字幕\n\n"
    )
    return header + "\n".join(lines)


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


# ── 入口 ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
