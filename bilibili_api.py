import requests
from typing import Dict, Any, Optional, List
from utils import Config, clean_text


class BilibiliAPI:
    """B站API交互类"""

    def __init__(self, config: Config):
        self.config = config
        self.base_url = "https://api.bilibili.com"
        self.headers = config.get_headers()
        self.cookies = config.get_cookies()

    def _request(self, url: str, params: dict = None) -> Optional[Dict[str, Any]]:
        """统一请求方法，带Cookie"""
        try:
            response = requests.get(
                url,
                headers=self.headers,
                cookies=self.cookies,
                params=params,
                timeout=self.config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"请求失败: {e}")
            return None

    def _request_with_headers(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        referer: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """带上下文请求头的请求，尽量贴近浏览器插件行为"""
        headers = dict(self.headers)
        if referer:
            headers["Referer"] = referer
            headers["Origin"] = "https://www.bilibili.com"

        try:
            response = requests.get(
                url,
                headers=headers,
                cookies=self.cookies,
                params=params,
                timeout=self.config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"请求失败: {e}")
            return None

    def get_video_info(self, video_id: str) -> Optional[Dict[str, Any]]:
        """获取视频基本信息"""
        if video_id.startswith("BV"):
            api_url = f"{self.base_url}/x/web-interface/view?bvid={video_id}"
        else:
            api_url = f"{self.base_url}/x/web-interface/view?aid={video_id[2:]}"

        data = self._request(api_url)
        if data and data.get("code") == 0:
            return data.get("data")

        print(f"API错误: {data.get('message', '未知错误') if data else '无响应'}")
        return None

    def get_subtitle_list(self, aid: Optional[int], cid: int, bvid: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        获取视频字幕列表

        关键API: /x/player/wbi/v2
        返回 data.subtitle.subtitles 数组，每个元素包含:
        - id: 字幕ID
        - lan: 语言代码 (ai-zh 表示AI生成)
        - lan_doc: 语言描述
        - subtitle_url: 字幕JSON的URL (已包含auth_key)
        - ai_type: AI字幕标识
        """
        # 多端点兜底，提升可用性（不同账号/风控环境下返回会有差异）
        endpoint_candidates = [
            (f"{self.base_url}/x/player/wbi/v2", {"aid": aid, "cid": cid}),
            (f"{self.base_url}/x/player/wbi/v2", {"bvid": bvid, "cid": cid}),
            (f"{self.base_url}/x/player/v2", {"aid": aid, "cid": cid}),
            (f"{self.base_url}/x/player/v2", {"bvid": bvid, "cid": cid}),
        ]

        for url, params in endpoint_candidates:
            clean_params = {k: v for k, v in params.items() if v is not None}
            if "cid" not in clean_params:
                continue

            data = self._request_with_headers(url, clean_params)
            if not data or data.get("code") != 0:
                continue

            subtitle_info = data.get("data", {}).get("subtitle", {})
            subtitles = subtitle_info.get("subtitles", [])
            available = [s for s in subtitles if s.get("subtitle_url")]
            if available:
                return available

        return None

    def get_subtitle_content(self, subtitle_url: str) -> Optional[Dict[str, Any]]:
        """
        下载字幕内容

        subtitle_url 已经是完整URL，包含auth_key，直接下载即可
        格式: https://aisubtitle.hdslb.com/bfs/ai_subtitle/prod/xxx?auth_key=xxx
        """
        # 处理相对URL
        if subtitle_url.startswith("//"):
            subtitle_url = "https:" + subtitle_url
        elif subtitle_url.startswith("/"):
            subtitle_url = "https://aisubtitle.hdslb.com" + subtitle_url

        request_strategies = [
            {
                "headers": {
                    **self.headers,
                    "Referer": "https://www.bilibili.com/",
                    "Origin": "https://www.bilibili.com"
                },
                "cookies": self.cookies
            },
            {
                "headers": {"User-Agent": self.headers.get("User-Agent", "Mozilla/5.0")},
                "cookies": {}
            },
            {
                "headers": {},
                "cookies": {}
            }
        ]

        last_error: Optional[Exception] = None
        for strategy in request_strategies:
            try:
                response = requests.get(
                    subtitle_url,
                    headers=strategy["headers"],
                    cookies=strategy["cookies"],
                    timeout=self.config.REQUEST_TIMEOUT
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                last_error = e
                continue

        if last_error:
            err = str(last_error)
            if "403" in err:
                print("下载字幕失败: 403（可能是auth_key过期或请求头不匹配）")
            else:
                print(f"下载字幕失败: {last_error}")
        return None

    def get_ai_subtitle_data(self, video_id: str, cid: int) -> Optional[Dict[str, Any]]:
        """
        获取AI字幕

        流程:
        1. 获取aid
        2. 调用 /x/player/wbi/v2 获取字幕列表
        3. 找到AI字幕 (lan 包含 "ai")
        4. 下载字幕URL
        """
        # 获取aid
        bvid = None
        if video_id.startswith("BV"):
            video_data = self.get_video_info(video_id)
            if not video_data:
                return None
            aid = video_data.get("aid")
            bvid = video_data.get("bvid") or video_id
        else:
            aid = int(video_id[2:]) if video_id.startswith("av") else int(video_id)
            bvid = None

        # 获取字幕列表
        subtitles = self.get_subtitle_list(aid=aid, cid=cid, bvid=bvid)
        if not subtitles:
            print("该视频没有字幕")
            return None

        # 优先找AI字幕
        ai_subtitle = None
        for sub in subtitles:
            lan = sub.get("lan", "").lower()
            if "ai" in lan:
                ai_subtitle = sub
                break

        # 如果没有AI字幕，用第一个可用字幕
        if not ai_subtitle:
            ai_subtitle = subtitles[0]
            print(f"没有AI字幕，使用: {ai_subtitle.get('lan_doc', '未知')}")

        # 下载字幕
        subtitle_url = ai_subtitle.get("subtitle_url")
        if not subtitle_url:
            return None

        subtitle_data = self.get_subtitle_content(subtitle_url)
        if not subtitle_data:
            return None

        # 返回原始结构，调用方可选择输出格式
        return {
            "subtitle_meta": ai_subtitle,
            "subtitle_data": subtitle_data
        }

    def get_ai_subtitle(self, video_id: str, cid: int) -> Optional[str]:
        """兼容旧接口：返回默认文本格式字幕"""
        subtitle_bundle = self.get_ai_subtitle_data(video_id, cid)
        if not subtitle_bundle:
            return None

        subtitle_data = subtitle_bundle.get("subtitle_data", {})
        return self._format_subtitle(subtitle_data)

    def _format_subtitle(self, subtitle_data: Dict[str, Any]) -> Optional[str]:
        """将字幕数据转换为文本格式"""
        body = subtitle_data.get("body", [])
        if not body:
            return None

        lines = []
        for item in body:
            from_time = item.get("from", 0)
            to_time = item.get("to", 0)
            content = item.get("content", "")

            start_str = self._format_timestamp(from_time)
            end_str = self._format_timestamp(to_time)
            lines.append(f"[{start_str} - {end_str}] {content}")

        return "\n".join(lines)

    def _format_timestamp(self, timestamp: float) -> str:
        """格式化时间戳为 HH:MM:SS 格式"""
        hours = int(timestamp // 3600)
        minutes = int((timestamp % 3600) // 60)
        seconds = int(timestamp % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class VideoInfo:
    """视频信息类"""

    def __init__(self, video_data: Dict[str, Any]):
        self.aid = video_data.get("aid")
        self.bvid = video_data.get("bvid")
        self.title = clean_text(video_data.get("title", ""))
        self.description = clean_text(video_data.get("desc", ""))
        self.duration = video_data.get("duration", 0)
        self.owner = video_data.get("owner", {}).get("name", "")
        self.pic = video_data.get("pic", "")
        self.pubdate = video_data.get("pubdate", 0)
        self.copyright = video_data.get("copyright", 1)
        self.pages = video_data.get("pages", [])

    def __str__(self):
        return f"视频标题: {self.title}\nUP主: {self.owner}\n描述: {self.description[:100]}..."

    def get_duration_formatted(self) -> str:
        """格式化视频时长"""
        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes}:{seconds:02d}"
