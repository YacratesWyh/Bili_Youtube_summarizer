import html
import json
import re
import requests
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bilibili_api import BilibiliAPI, VideoInfo
from utils import Config, clean_text


class BaseSubtitleAdapter(ABC):
    """统一字幕适配器接口"""

    name = "base"

    @abstractmethod
    def matches(self, video_url: str) -> bool:
        pass

    @abstractmethod
    def fetch_subtitle_bundle(self, video_url: str) -> Optional[Dict[str, Any]]:
        pass


class BilibiliSubtitleAdapter(BaseSubtitleAdapter):
    name = "bilibili"

    def __init__(self, config: Config):
        self.config = config
        self.api = BilibiliAPI(config)

    def matches(self, video_url: str) -> bool:
        return (
            "bilibili.com/video/" in video_url
            or "aisubtitle.hdslb.com/bfs/ai_subtitle/" in video_url
            or bool(re.search(r"(BV[a-zA-Z0-9]+|av\d+)", video_url))
        )

    def fetch_subtitle_bundle(self, video_url: str) -> Optional[Dict[str, Any]]:
        # 允许直接使用 B 站 ai_subtitle 直链，快速绕过字幕列表接口
        if "aisubtitle.hdslb.com/bfs/ai_subtitle/" in video_url:
            subtitle_data = self.api.get_subtitle_content(video_url)
            if not subtitle_data:
                return None
            return {
                "platform": self.name,
                "video_info": {
                    "title": "Bilibili AI Subtitle",
                    "owner": "",
                    "duration": 0,
                    "description": "字幕直链导入"
                },
                "subtitle_meta": {"lan": subtitle_data.get("lang", ""), "lan_doc": "AI字幕直链"},
                "subtitle_data": subtitle_data,
                "source": "subtitle"
            }

        video_id = self._extract_video_id(video_url)
        if not video_id:
            return None

        if not self.config.has_bilibili_cookies():
            print("警告: 未配置B站Cookie，可能无法获取AI字幕")
            print("请在.env文件中配置 BILIBILI_COOKIE（整段Cookie）")

        video_data = self.api.get_video_info(video_id)
        if not video_data:
            return None

        video_info = VideoInfo(video_data)
        pages = video_info.pages or [{"cid": video_data.get("cid")}]
        cid = pages[0].get("cid")
        if not cid:
            return None

        print("尝试获取字幕（含AI字幕）...")
        subtitle_bundle = self.api.get_ai_subtitle_data(video_id, cid)
        if not subtitle_bundle:
            return None

        subtitle_meta = subtitle_bundle.get("subtitle_meta", {})
        subtitle_data = subtitle_bundle.get("subtitle_data", {})

        return {
            "platform": self.name,
            "video_info": {
                "title": video_info.title,
                "owner": video_info.owner,
                "duration": video_info.duration,
                "description": video_info.description
            },
            "subtitle_meta": subtitle_meta,
            "subtitle_data": subtitle_data,
            "source": "subtitle"
        }

    def _extract_video_id(self, url: str) -> Optional[str]:
        patterns = [
            r'https://www\.bilibili\.com/video/(BV[a-zA-Z0-9]+)',
            r'https://www\.bilibili\.com/video/(av\d+)',
            r'(BV[a-zA-Z0-9]+)',
            r'(av\d+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None


class YoutubeSubtitleAdapter(BaseSubtitleAdapter):
    name = "youtube"

    def __init__(self, config: Config):
        self.config = config
        self.headers = config.get_headers()

    def matches(self, video_url: str) -> bool:
        return "youtube.com/watch" in video_url or "youtu.be/" in video_url or "youtube.com/shorts/" in video_url

    def fetch_subtitle_bundle(self, video_url: str) -> Optional[Dict[str, Any]]:
        video_id = self._extract_video_id(video_url)
        if not video_id:
            return None

        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        html_text = self._get_watch_page(watch_url)
        if not html_text:
            return None

        player_response = self._extract_player_response(html_text)
        if not player_response:
            print("无法解析YouTube播放器响应")
            return None

        video_details = player_response.get("videoDetails", {})
        tracklist = player_response.get("captions", {}).get("playerCaptionsTracklistRenderer", {})
        caption_tracks = tracklist.get("captionTracks", [])
        if not caption_tracks:
            print("YouTube视频没有可用字幕轨道")
            return None

        selected_track = self._pick_caption_track(caption_tracks)
        if not selected_track:
            return None

        subtitle_data = self._download_caption_track(selected_track)
        if not subtitle_data:
            return None

        return {
            "platform": self.name,
            "video_info": {
                "title": clean_text(video_details.get("title", "")),
                "owner": clean_text(video_details.get("author", "")),
                "duration": int(video_details.get("lengthSeconds", 0) or 0),
                "description": clean_text(video_details.get("shortDescription", ""))
            },
            "subtitle_meta": {
                "lan": selected_track.get("languageCode"),
                "lan_doc": selected_track.get("name", {}).get("simpleText", ""),
                "kind": selected_track.get("kind", "")
            },
            "subtitle_data": subtitle_data,
            "source": "subtitle"
        }

    def _extract_video_id(self, url: str) -> Optional[str]:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path = parsed.path

        if "youtu.be" in host:
            vid = path.strip("/").split("/")[0]
            return vid or None

        if "youtube.com" in host:
            if path == "/watch":
                q = parse_qs(parsed.query)
                vid = (q.get("v") or [None])[0]
                return vid
            if path.startswith("/shorts/"):
                parts = path.split("/")
                return parts[2] if len(parts) > 2 and parts[2] else None

        return None

    def _get_watch_page(self, watch_url: str) -> Optional[str]:
        try:
            response = requests.get(
                watch_url,
                headers=self.headers,
                timeout=self.config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"获取YouTube页面失败: {e}")
            return None

    def _extract_player_response(self, page_html: str) -> Optional[Dict[str, Any]]:
        markers = ["ytInitialPlayerResponse = ", '"ytInitialPlayerResponse":']
        for marker in markers:
            payload = self._extract_json_object_by_marker(page_html, marker)
            if not payload:
                continue
            try:
                return json.loads(payload)
            except Exception:
                continue
        return None

    def _extract_json_object_by_marker(self, text: str, marker: str) -> Optional[str]:
        start_idx = text.find(marker)
        if start_idx < 0:
            return None

        brace_start = text.find("{", start_idx)
        if brace_start < 0:
            return None

        depth = 0
        in_string = False
        escape = False
        for idx in range(brace_start, len(text)):
            ch = text[idx]

            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == "\"":
                    in_string = False
                continue

            if ch == "\"":
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[brace_start:idx + 1]

        return None

    def _pick_caption_track(self, tracks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        preferred_lang_prefix = ["zh", "en"]

        def lang_score(track: Dict[str, Any]) -> int:
            lang = str(track.get("languageCode", "")).lower()
            for i, prefix in enumerate(preferred_lang_prefix):
                if lang.startswith(prefix):
                    return i
            return 99

        sorted_tracks = sorted(
            tracks,
            key=lambda t: (
                1 if t.get("kind") == "asr" else 0,
                lang_score(t)
            )
        )
        return sorted_tracks[0] if sorted_tracks else None

    def _ensure_json3_url(self, base_url: str) -> str:
        unescaped = html.unescape(base_url.replace("\\u0026", "&"))
        parsed = urlparse(unescaped)
        query = parse_qs(parsed.query)
        query["fmt"] = ["json3"]
        new_query = urlencode(query, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    def _download_caption_track(self, track: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        base_url = track.get("baseUrl")
        if not base_url:
            return None

        track_url = self._ensure_json3_url(base_url)
        try:
            response = requests.get(track_url, headers=self.headers, timeout=self.config.REQUEST_TIMEOUT)
            response.raise_for_status()
            payload = response.json()
        except Exception as e:
            print(f"下载YouTube字幕失败: {e}")
            return None

        body = []
        for event in payload.get("events", []):
            segments = event.get("segs", [])
            if not segments:
                continue

            text = "".join(seg.get("utf8", "") for seg in segments).replace("\n", " ").strip()
            text = clean_text(text)
            if not text:
                continue

            start_ms = int(event.get("tStartMs", 0) or 0)
            duration_ms = int(event.get("dDurationMs", 0) or 0)
            end_ms = start_ms + (duration_ms if duration_ms > 0 else 1500)
            body.append({
                "from": start_ms / 1000.0,
                "to": end_ms / 1000.0,
                "content": text
            })

        if not body:
            return None
        return {"body": body}


class SubtitleExtractor:
    """字幕提取类（统一Adapter入口）"""

    def __init__(self, config: Config):
        self.config = config
        # 延迟初始化：避免仅命中缓存时也触发B站登录态读取
        self.adapters: Optional[List[BaseSubtitleAdapter]] = None

    def _ensure_adapters(self) -> List[BaseSubtitleAdapter]:
        if self.adapters is None:
            self.adapters = [
                BilibiliSubtitleAdapter(self.config),
                YoutubeSubtitleAdapter(self.config),
            ]
        return self.adapters

    def extract_subtitles(self, video_url: str, subtitle_format: str = "srt") -> Optional[Dict[str, Any]]:
        """从视频URL提取字幕（自动选择平台适配器）"""
        adapter = self._pick_adapter(video_url)
        if not adapter:
            print("不支持的视频平台URL")
            return None

        subtitle_bundle = adapter.fetch_subtitle_bundle(video_url)
        if not subtitle_bundle:
            print("该视频没有可用字幕")
            return None

        subtitle_meta = subtitle_bundle.get("subtitle_meta", {})
        subtitle_data_raw = subtitle_bundle.get("subtitle_data", {})
        body = subtitle_data_raw.get("body", [])
        subtitle_text = self._format_subtitle_body(body, subtitle_format)
        if not subtitle_text:
            return None

        video_info = subtitle_bundle.get("video_info", {})
        subtitles = [{
            "page": 1,
            "part": "1",
            "title": video_info.get("title", ""),
            "subtitles": subtitle_text,
            "body": body,
            "source": subtitle_bundle.get("source", "subtitle"),
            "format": subtitle_format,
            "language": subtitle_meta.get("lan"),
            "language_name": subtitle_meta.get("lan_doc"),
            "is_ai": "ai" in str(subtitle_meta.get("lan", "")).lower()
        }]

        print(f"成功获取字幕（平台: {subtitle_bundle.get('platform', adapter.name)}）")
        return {
            "video_info": video_info,
            "subtitles": subtitles,
            "source": subtitle_bundle.get("source", "subtitle"),
            "platform": subtitle_bundle.get("platform", adapter.name)
        }

    def _pick_adapter(self, video_url: str) -> Optional[BaseSubtitleAdapter]:
        for adapter in self._ensure_adapters():
            if adapter.matches(video_url):
                return adapter
        return None

    def _format_subtitle_body(self, body: List[Dict[str, Any]], subtitle_format: str) -> Optional[str]:
        """将B站字幕body按目标格式输出"""
        if not body:
            return None

        fmt = (subtitle_format or "txt").lower()
        lines = []

        if fmt == "txt":
            for item in body:
                from_time = item.get("from", 0)
                to_time = item.get("to", 0)
                content = item.get("content", "")
                start_str = self._format_timestamp(from_time)
                end_str = self._format_timestamp(to_time)
                lines.append(f"[{start_str} - {end_str}] {content}")
            return "\n".join(lines)

        if fmt == "srt":
            for index, item in enumerate(body, start=1):
                from_time = item.get("from", 0)
                to_time = item.get("to", 0)
                content = item.get("content", "")
                start_str = self._format_timestamp_srt(from_time)
                end_str = self._format_timestamp_srt(to_time)
                lines.extend([str(index), f"{start_str} --> {end_str}", content, ""])
            return "\n".join(lines).strip()

        if fmt == "vtt":
            lines.append("WEBVTT")
            lines.append("")
            for item in body:
                from_time = item.get("from", 0)
                to_time = item.get("to", 0)
                content = item.get("content", "")
                start_str = self._format_timestamp_vtt(from_time)
                end_str = self._format_timestamp_vtt(to_time)
                lines.extend([f"{start_str} --> {end_str}", content, ""])
            return "\n".join(lines).strip()

        if fmt == "lrc":
            for item in body:
                from_time = item.get("from", 0)
                content = item.get("content", "")
                start_str = self._format_timestamp_lrc(from_time)
                lines.append(f"[{start_str}] {content}")
            return "\n".join(lines)

        # 未知格式时回退到原有txt，避免破坏现有行为
        return self._format_subtitle_body(body, "txt")

    def _format_timestamp(self, seconds: float) -> str:
        """格式化时间戳为 HH:MM:SS"""
        total_seconds = max(0, int(seconds))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _format_timestamp_srt(self, seconds: float) -> str:
        """格式化时间戳为 SRT: HH:MM:SS,mmm"""
        safe = max(0.0, float(seconds))
        whole = int(safe)
        ms = int(round((safe - whole) * 1000))
        if ms == 1000:
            whole += 1
            ms = 0
        hours = whole // 3600
        minutes = (whole % 3600) // 60
        secs = whole % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"

    def _format_timestamp_vtt(self, seconds: float) -> str:
        """格式化时间戳为 VTT: HH:MM:SS.mmm"""
        return self._format_timestamp_srt(seconds).replace(",", ".")

    def _format_timestamp_lrc(self, seconds: float) -> str:
        """格式化时间戳为 LRC: MM:SS.xx"""
        safe = max(0.0, float(seconds))
        minutes = int(safe // 60)
        sec_float = safe % 60
        secs = int(sec_float)
        centis = int(round((sec_float - secs) * 100))
        if centis == 100:
            secs += 1
            centis = 0
        if secs == 60:
            minutes += 1
            secs = 0
        return f"{minutes:02d}:{secs:02d}.{centis:02d}"

    def extract_text_from_subtitles(self, subtitle_data: Dict[str, Any]) -> str:
        """从字幕数据中提取纯文本"""
        subtitles = subtitle_data.get("subtitles", [])
        text_parts = []

        for page_data in subtitles:
            page_title = page_data.get("title", "")
            subtitle_text = page_data.get("subtitles", "")

            if page_title:
                text_parts.append(f"## {page_title}")

            if subtitle_text:
                lines = subtitle_text.split('\n')
                clean_lines = []

                for line in lines:
                    clean_line = re.sub(r'^\[\d{2}:\d{2}:\d{2} - \d{2}:\d{2}:\d{2}\]\s*', '', line)
                    clean_line = clean_text(clean_line)

                    if clean_line:
                        clean_lines.append(clean_line)

                if clean_lines:
                    text_parts.append("\n".join(clean_lines))

        return "\n\n".join(text_parts)

    def save_subtitles_to_file(self, subtitle_data: Dict[str, Any], output_path: str) -> bool:
        """保存字幕到文件"""
        try:
            subtitles = subtitle_data.get("subtitles", [])
            first_page = subtitles[0] if subtitles else {}
            output_format = str(first_page.get("format", "txt")).lower()

            video_info = subtitle_data.get("video_info", {})
            title = video_info.get("title", "未知标题")
            owner = video_info.get("owner", "未知UP主")
            duration = video_info.get("duration", 0)

            minutes = duration // 60
            seconds = duration % 60
            duration_str = f"{minutes}:{seconds:02d}"

            # 结构化字幕格式(srt/vtt/lrc)直接输出正文，避免污染标准格式
            if output_format in {"srt", "vtt", "lrc"}:
                final_content = first_page.get("subtitles", "")
            else:
                text_content = self.extract_text_from_subtitles(subtitle_data)
                final_content = f"# {title}\n\n"
                final_content += f"UP主: {owner}\n"
                final_content += f"时长: {duration_str}\n\n"
                final_content += "## 视频内容\n\n"
                final_content += text_content

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_content)

            return True

        except Exception as e:
            print(f"保存字幕文件失败: {e}")
            return False

    def save_subtitles_to_markdown(self, subtitle_data: Dict[str, Any], output_path: str) -> bool:
        """保存字幕为更易读的Markdown格式"""
        try:
            video_info = subtitle_data.get("video_info", {})
            title = video_info.get("title", "未知标题")
            owner = video_info.get("owner", "未知UP主")
            duration = int(video_info.get("duration", 0) or 0)
            source = subtitle_data.get("source", "subtitle")
            platform = subtitle_data.get("platform", "unknown")

            minutes = duration // 60
            seconds = duration % 60
            duration_str = f"{minutes}:{seconds:02d}"

            subtitles = subtitle_data.get("subtitles", [])
            first_page = subtitles[0] if subtitles else {}
            subtitle_text = str(first_page.get("subtitles", "") or "")
            output_format = str(first_page.get("format", "srt")).lower()
            subtitle_body = first_page.get("body", [])

            md_lines = [
                f"# {title}",
                "",
                f"- 平台: `{platform}`",
                f"- 来源: `{source}`",
                f"- UP主/作者: `{owner}`",
                f"- 时长: `{duration_str}`",
                "",
                "## 字幕内容",
                "",
            ]

            if isinstance(subtitle_body, list) and subtitle_body:
                # 阅读版：每行只保留一个时间（开始时间）+ 文本
                for item in subtitle_body:
                    start_time = self._format_timestamp(item.get("from", 0))
                    content = clean_text(str(item.get("content", "")))
                    if content:
                        md_lines.append(f"- [{start_time}] {content}")
            else:
                # 回退：没有原始body时，从文本中做轻量清洗
                for line in subtitle_text.split("\n"):
                    clean_line = line.strip()
                    if clean_line:
                        clean_line = re.sub(r"^\d+\s*$", "", clean_line).strip()
                        clean_line = re.sub(
                            r"^\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*$",
                            "",
                            clean_line
                        ).strip()
                        if clean_line:
                            md_lines.append(f"- {clean_line}")

            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(md_lines).rstrip() + "\n")

            return True
        except Exception as e:
            print(f"保存Markdown字幕文件失败: {e}")
            return False

    def save_subtitles_to_json(self, subtitle_data: Dict[str, Any], output_path: str) -> bool:
        """保存字幕到JSON文件"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(subtitle_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存JSON字幕文件失败: {e}")
            return False
