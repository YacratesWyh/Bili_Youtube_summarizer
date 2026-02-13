import os
import re
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    """配置管理类"""
    
    def __init__(self):
        # AI总结配置：兼容旧字段 OPENAI_API_KEY
        self.AI_API_KEY = os.getenv("AI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        self.AI_BASE_URL = os.getenv("AI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
        self.OUTPUT_DIR = "output"
        self.LOG_FILE = "app.log"
        self.DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "GLM-4.7")
        self.REQUEST_TIMEOUT = 30  # 请求超时时间（秒）
        self.MAX_RETRY = 3  # 最大重试次数
        
        # B站Cookie配置（获取AI字幕必需）
        self.BILIBILI_COOKIE = os.getenv("BILIBILI_COOKIE", "")
        self.BILIBILI_COOKIE_FILE = os.getenv("BILIBILI_COOKIE_FILE", "")
        self.BILIBILI_AUTO_COOKIE = os.getenv("BILIBILI_AUTO_COOKIE", "0").lower() in {"1", "true", "yes", "on"}
        self._browser_cookie_cache: Optional[Dict[str, str]] = None
        
        # 确保输出目录存在
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
    
    def get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.bilibili.com"
        }
    
    def get_cookies(self) -> Dict[str, str]:
        """获取B站Cookie"""
        cookies = self._parse_cookie_header(self.BILIBILI_COOKIE)

        # 允许直接从浏览器导出的cookie JSON文件加载（默认 key.json）
        if "SESSDATA" not in cookies:
            file_cookies = self._load_bilibili_cookie_file()
            cookies.update(file_cookies)

        # 自动读取浏览器登录态默认关闭（跨机器部署常失败）
        if "SESSDATA" not in cookies and self.BILIBILI_AUTO_COOKIE:
            auto_cookies = self._load_bilibili_cookie_from_browser()
            cookies.update(auto_cookies)

        return cookies
    
    def has_bilibili_cookies(self) -> bool:
        """检查是否配置了B站Cookie"""
        cookies = self.get_cookies()
        # 不再绑定固定字段名，只要存在可用登录态即可
        return bool(cookies.get("SESSDATA") or cookies.get("DedeUserID") or cookies.get("bili_jct"))

    def _parse_cookie_header(self, cookie_header: str) -> Dict[str, str]:
        """解析 Cookie 请求头字符串为字典"""
        parsed: Dict[str, str] = {}
        if not cookie_header:
            return parsed

        for part in cookie_header.split(";"):
            piece = part.strip()
            if not piece or "=" not in piece:
                continue
            name, value = piece.split("=", 1)
            name = name.strip()
            value = value.strip()
            if name and value:
                parsed[name] = value

        return parsed

    def _load_bilibili_cookie_from_browser(self) -> Dict[str, str]:
        """自动从本机浏览器读取bilibili登录态Cookie"""
        if self._browser_cookie_cache is not None:
            return dict(self._browser_cookie_cache)

        cookie_names = {"SESSDATA", "bili_jct", "DedeUserID", "buvid3", "buvid4", "b_nut", "b_lsid"}

        try:
            import browser_cookie3  # type: ignore
        except Exception:
            self._browser_cookie_cache = {}
            return {}

        browser_readers = [
            ("Edge", browser_cookie3.edge),
            ("Chrome", browser_cookie3.chrome),
            ("Firefox", browser_cookie3.firefox),
        ]

        for browser_name, reader in browser_readers:
            try:
                jar = reader(domain_name="bilibili.com")
                parsed: Dict[str, str] = {}
                for item in jar:
                    if item.name in cookie_names and item.value:
                        parsed[item.name] = item.value

                if parsed.get("SESSDATA"):
                    print(f"已自动从{browser_name}读取登录态Cookie")
                    self._browser_cookie_cache = parsed
                    return dict(parsed)
            except Exception:
                continue

        self._browser_cookie_cache = {}
        return {}

    def _load_bilibili_cookie_file(self) -> Dict[str, str]:
        """从导出的cookie JSON文件加载bilibili cookies"""
        cookie_path = self._resolve_cookie_file_path()
        if not cookie_path:
            return {}

        try:
            with open(cookie_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if not isinstance(payload, list):
                return {}

            parsed: Dict[str, str] = {}
            for item in payload:
                if not isinstance(item, dict):
                    continue
                domain = str(item.get("domain", ""))
                if "bilibili.com" not in domain:
                    continue
                name = str(item.get("name", "")).strip()
                value = str(item.get("value", "")).strip()
                if name and value:
                    parsed[name] = value

            if parsed.get("SESSDATA"):
                print(f"已从cookie文件加载登录态: {cookie_path}")
            return parsed
        except Exception as e:
            print(f"读取cookie文件失败: {e}")
            return {}

    def _resolve_cookie_file_path(self) -> Optional[Path]:
        """解析cookie文件路径：显式配置优先，否则自动探测常见文件名"""
        if self.BILIBILI_COOKIE_FILE:
            path = Path(self.BILIBILI_COOKIE_FILE)
            if not path.is_absolute():
                path = Path.cwd() / path
            return path if path.exists() else None

        candidates = ["key.json", "key2.json", "cookies.json", "bilibili_cookies.json"]
        for name in candidates:
            p = Path.cwd() / name
            if p.exists():
                return p
        return None


# 配置日志
def setup_logging(log_file: str = "app.log", verbose: bool = False) -> logging.Logger:
    """设置日志配置"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("VideoSummary")

# 正则表达式模式
BV_PATTERN = re.compile(r'BV([a-zA-Z0-9]+)')
AV_PATTERN = re.compile(r'av(\d+)')
URL_PATTERN = re.compile(r'https://www\.bilibili\.com/video/(BV[a-zA-Z0-9]+|av\d+)')

def extract_video_id(url: str) -> Optional[str]:
    """从URL中提取视频ID"""
    match = URL_PATTERN.search(url)
    if match:
        return match.group(1)
    
    # 如果是纯BV号或AV号
    bv_match = BV_PATTERN.search(url)
    if bv_match:
        return f"BV{bv_match.group(1)}"
    
    av_match = AV_PATTERN.search(url)
    if av_match:
        return f"av{av_match.group(1)}"
    
    return None

def clean_text(text: str) -> str:
    """清理文本，去除多余空白和特殊字符"""
    if not text:
        return ""
    # 去除HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    # 去除多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    return text