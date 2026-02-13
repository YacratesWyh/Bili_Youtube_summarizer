from typing import Dict, Any, Optional, List
import re
import requests
from utils import Config, clean_text

class VideoSummarizer:
    """视频内容总结类"""
    
    def __init__(self, config: Config):
        self.config = config
        self.ai_api_key = config.AI_API_KEY
        self.ai_base_url = config.AI_BASE_URL
        self.default_model = config.DEFAULT_MODEL
    
    def summarize_video(self, subtitle_data: Dict[str, Any], model: Optional[str] = None) -> Optional[str]:
        """总结视频内容"""
        if not self.ai_api_key:
            print("未配置AI API密钥，无法进行AI总结")
            return None
        
        # 提取文本内容
        video_info = subtitle_data.get("video_info", {})
        title = video_info.get("title", "")
        description = video_info.get("description", "")
        
        # 从字幕中提取文本
        text_content = self._extract_text_content(subtitle_data)
        
        if not text_content:
            print("没有可用的字幕内容")
            return None
        
        # 构建总结提示
        prompt = self._build_summary_prompt(title, description, text_content)
        
        # 使用指定的模型或默认模型
        model_name = model or self.default_model
        
        # 调用API进行总结
        return self._call_ai_api(prompt, model_name)

    def chat(self, user_message: str, model: Optional[str] = None, history: Optional[List[Dict[str, str]]] = None) -> Optional[str]:
        """与大模型进行通用对话"""
        message = (user_message or "").strip()
        if not message:
            return None
        model_name = model or self.default_model
        system_prompt = "你是一个专业、简洁、可靠的中文助手。请直接回答用户问题。"
        messages: List[Dict[str, str]] = []
        if history:
            for item in history:
                role = str(item.get("role", "")).strip()
                content = str(item.get("content", "")).strip()
                if role in {"system", "user", "assistant"} and content:
                    messages.append({"role": role, "content": content})
        if not any(m.get("role") == "system" for m in messages):
            messages.insert(0, {"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        return self._call_ai_api_messages(messages, model_name)
    
    def _extract_text_content(self, subtitle_data: Dict[str, Any]) -> str:
        """从字幕数据中提取纯文本"""
        subtitles = subtitle_data.get("subtitles", [])
        text_parts = []
        
        for page_data in subtitles:
            subtitle_text = page_data.get("subtitles", "")
            
            if subtitle_text:
                # 从带时间戳的字幕中提取纯文本
                lines = subtitle_text.split('\n')
                clean_lines = []
                
                for line in lines:
                    # 先剥离字幕序号与时间戳，避免无意义token进入prompt
                    line = self._strip_timestamps(line)
                    # 移除时间戳部分，只保留文本
                    clean_line = clean_text(line)
                    if clean_line and not clean_line.startswith('['):
                        clean_lines.append(clean_line)
                
                if clean_lines:
                    text_parts.append("\n".join(clean_lines))
        
        return "\n\n".join(text_parts)

    def _strip_timestamps(self, line: str) -> str:
        """删除常见字幕时间戳与序号"""
        s = (line or "").strip()
        if not s:
            return ""
        if s.isdigit():
            return ""
        # SRT/VTT区间：00:00:01,000 --> 00:00:03,200
        if "-->" in s:
            return ""
        # [00:12] / [01:02:03] / [00:01.23] 这类标签
        s = re.sub(r"\[\s*\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?\s*\]", "", s)
        # 行内裸时间：00:12 / 01:02:03 / 00:12.34 / 00:12,340
        s = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?\b", "", s)
        return s.strip()
    
    def _build_summary_prompt(self, title: str, description: str, content: str) -> str:
        """构建总结提示"""
        prompt = f"""请根据以下B站视频的字幕内容，生成一个简洁明了的总结：

视频标题：{title}
视频描述：{description}

字幕内容：
{content}

请提供一个结构化的总结，包括：
1. 主要内容概述
2. 关键点提取
3. 适合的标签（用逗号分隔）

总结应该简洁明了，字数控制在500字以内。
重要：只输出最终总结，不要输出思考过程、推理步骤或分析草稿。"""
        
        return prompt
    
    def _call_ai_api(self, prompt: str, model: Optional[str], system_prompt: Optional[str] = None) -> Optional[str]:
        """按智谱文档的HTTP Bearer方式调用 chat/completions（无兜底）"""
        messages = [
            {
                "role": "system",
                "content": system_prompt or "你是一个专业的视频内容总结助手，擅长提取视频的核心内容并生成简洁的总结。"
            },
            {"role": "user", "content": prompt}
        ]
        return self._call_ai_api_messages(messages, model)

    def _call_ai_api_messages(self, messages: List[Dict[str, str]], model: Optional[str]) -> Optional[str]:
        """按messages调用 chat/completions（无兜底）"""
        model_name = model or self.default_model
        base_url = (self.ai_base_url or "").rstrip("/")
        endpoint = f"{base_url}/chat/completions"
        api_key = (self.ai_api_key or "").strip()
        if api_key.lower().startswith("bearer "):
            # 兼容用户直接粘贴 "Bearer xxx"
            api_key = api_key[7:].strip()
        if not api_key:
            print("AI API Key 为空，请在GUI或 .env 中配置有效密钥")
            return None
        try:
            # requests/http.client 发送header时使用 latin-1，提前校验并给出可读错误
            api_key.encode("latin-1")
        except UnicodeEncodeError:
            print("AI API Key 包含非法字符（例如中文或全角字符），请粘贴原始英文密钥")
            return None

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1500,
                "stream": False
            }
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=self.config.REQUEST_TIMEOUT
            )
            if response.status_code >= 400:
                raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")

            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                raise RuntimeError(f"响应缺少choices: {str(data)[:500]}")
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            text = str(content).strip() if content else ""
            if not text:
                reasoning = message.get("reasoning_content")
                if isinstance(reasoning, list):
                    reasoning = "".join(
                        part.get("text", "") if isinstance(part, dict) else str(part)
                        for part in reasoning
                    )
                reasoning_text = str(reasoning).strip() if reasoning else ""
                if reasoning_text:
                    print(f"警告: content为空，回退使用reasoning_content（model={model_name}）")
                    return reasoning_text
            if not text:
                finish_reason = choices[0].get("finish_reason")
                print(f"AI返回空内容（model={model_name}, finish_reason={finish_reason}）")
                print(f"响应片段: {str(data)[:500]}")
                return None
            return text
        except Exception as e:
            print(f"调用AI API失败（model={model_name}）: {e}")
            if "/api/coding/paas/v4" in base_url:
                print("提示：当前使用的是 coding 端点，通用总结建议改为 https://open.bigmodel.cn/api/paas/v4")
            return None
    
    def _local_summarize(self, subtitle_data: Dict[str, Any]) -> Optional[str]:
        """本地总结方法（不使用外部API）"""
        # 提取视频信息
        video_info = subtitle_data.get("video_info", {})
        title = video_info.get("title", "")
        description = video_info.get("description", "")
        
        # 提取文本内容
        text_content = self._extract_text_content(subtitle_data)
        
        if not text_content:
            return None
        
        # 构建总结
        summary = f"## 视频信息\n\n"
        summary += f"**标题**: {title}\n\n"
        
        if description:
            summary += f"**描述**: {description[:200]}...\n\n"
        
        summary += f"## 内容摘要\n\n"
        
        # 简单的关键词提取和总结
        lines = text_content.split('\n')
        total_lines = len(lines)
        
        # 取前10%和后10%的内容作为开头和结尾
        intro_lines = lines[:max(5, total_lines // 10)]
        outro_lines = lines[-max(5, total_lines // 10):]
        
        summary += "### 开头内容\n\n"
        summary += "\n".join(intro_lines) + "\n\n"
        
        summary += "### 结尾内容\n\n"
        summary += "\n".join(outro_lines) + "\n\n"
        
        # 提取可能的关键词
        words = text_content.split()
        word_freq = {}
        
        for word in words:
            if len(word) > 2:  # 忽略短词
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # 获取最常见的词作为关键词
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        top_keywords = [word for word, freq in sorted_words[:10] if freq > 2]
        
        if top_keywords:
            summary += "### 关键词\n\n"
            summary += ", ".join(top_keywords) + "\n\n"
        
        summary += "### 注意事项\n\n"
        summary += "这是一个基于字幕内容的自动生成摘要，可能不完整或不准确。建议结合视频内容进行理解。\n"
        
        return summary
    
    def _local_summarize_from_content(self, prompt: str) -> Optional[str]:
        """从提示内容中提取信息进行本地总结"""
        # 简单地从提示中提取标题和描述
        lines = prompt.split('\n')
        title = ""
        description = ""
        content = ""
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            if line.startswith("视频标题："):
                title = line.replace("视频标题：", "").strip()
            elif line.startswith("视频描述："):
                description = line.replace("视频描述：", "").strip()
                current_section = "description"
            elif line.startswith("字幕内容："):
                current_section = "content"
            elif current_section == "content" and line:
                if content:
                    content += "\n" + line
                else:
                    content = line
        
        # 生成简单总结
        summary = f"## 视频信息\n\n"
        summary += f"**标题**: {title}\n\n"
        
        if description:
            summary += f"**描述**: {description}\n\n"
        
        summary += f"## 内容摘要\n\n"
        
        if content:
            # 提取前几行作为摘要
            content_lines = content.split('\n')
            summary += "\n".join(content_lines[:10]) + "\n\n"
        
        summary += "### 注意事项\n\n"
        summary += "这是一个基于字幕内容的自动生成摘要，可能不完整或不准确。建议结合视频内容进行理解。\n"
        
        return summary
    
    def save_summary_to_file(self, summary: str, subtitle_data: Dict[str, Any], output_path: str) -> bool:
        """保存总结到文件"""
        try:
            # 提取视频信息
            video_info = subtitle_data.get("video_info", {})
            title = video_info.get("title", "未知标题")
            owner = video_info.get("owner", "未知UP主")
            duration = video_info.get("duration", 0)
            
            # 格式化时长
            minutes = duration // 60
            seconds = duration % 60
            duration_str = f"{minutes}:{seconds:02d}"
            
            # 构建最终内容
            final_content = f"# {title} - 视频总结\n\n"
            final_content += f"**UP主**: {owner}\n"
            final_content += f"**时长**: {duration_str}\n\n"
            final_content += summary
            
            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_content)
            
            return True
            
        except Exception as e:
            print(f"保存总结文件失败: {e}")
            return False