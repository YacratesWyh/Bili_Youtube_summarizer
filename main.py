import argparse
import sys
import os
import re
import json
from pathlib import Path
from utils import Config, setup_logging
from subtitle_extractor import SubtitleExtractor
from video_summarizer import VideoSummarizer
from error_handlers import ErrorHandler, retry_on_failure, validate_url


def extract_url_identifier(url: str) -> str:
    """从URL提取稳定标识（优先BV号）用于输出文件命名"""
    bv_match = re.search(r"(BV[a-zA-Z0-9]+)", url)
    if bv_match:
        return bv_match.group(1)

    yt_match = re.search(r"[?&]v=([a-zA-Z0-9_-]{6,})", url)
    if yt_match:
        return yt_match.group(1)

    short_match = re.search(r"youtu\.be/([a-zA-Z0-9_-]{6,})", url)
    if short_match:
        return short_match.group(1)

    return ""


def get_subtitle_cache_path(config: Config, identifier: str) -> str:
    """按视频ID生成字幕缓存路径"""
    return str(Path(config.OUTPUT_DIR) / f"{identifier}_subtitles.cache.json")


def load_subtitle_cache(cache_path: str):
    """读取字幕缓存，失败返回None"""
    try:
        if not os.path.exists(cache_path):
            return None
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        if "subtitles" not in data or "video_info" not in data:
            return None
        return data
    except Exception:
        return None


def save_subtitle_cache(cache_path: str, subtitle_data: dict) -> bool:
    """保存字幕缓存，失败返回False"""
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(subtitle_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="视频字幕获取与总结工具（Bilibili/YouTube）")
    parser.add_argument("-u", "--url", required=True, help="视频URL（Bilibili/YouTube）")
    parser.add_argument("-o", "--output", help="输出文件路径（可选）")
    parser.add_argument("-m", "--model", help="使用的AI模型（可选）")
    parser.add_argument("--api-key", help="AI API Key（可选，优先于.env）")
    parser.add_argument("--api-base-url", help="AI API地址（可选，优先于.env）")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出模式")
    parser.add_argument("--no-summary", action="store_true", help="不生成总结，只获取字幕")
    parser.add_argument("--json", action="store_true", help="保存为JSON格式")
    parser.add_argument(
        "--subtitle-format",
        choices=["txt", "srt", "vtt", "lrc"],
        default="srt",
        help="保留兼容参数；当前固定按 srt 导出字幕"
    )
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging(verbose=args.verbose)
    error_handler = ErrorHandler(logger)

    step_no = [0]

    def log_step(message: str):
        """输出分阶段命令行日志，便于定位当前步骤"""
        step_no[0] += 1
        print(f"[步骤 {step_no[0]}] {message}")
        logger.info(f"[步骤 {step_no[0]}] {message}")
    
    try:
        log_step("开始处理请求")

        # 验证URL
        log_step("校验视频URL")
        validate_url(args.url)
        
        # 初始化配置
        log_step("加载配置")
        config = Config()
        if args.api_key is not None:
            config.AI_API_KEY = args.api_key.strip()
        if args.api_base_url is not None and args.api_base_url.strip():
            config.AI_BASE_URL = args.api_base_url.strip()

        print(f"正在处理视频: {args.url}")

        # 先用URL提取稳定ID，便于命中 output 缓存
        log_step("检查字幕缓存")
        identifier = extract_url_identifier(args.url)
        subtitle_data = None
        subtitle_cache_path = ""
        subtitle_cache_hit = False
        if identifier:
            subtitle_cache_path = get_subtitle_cache_path(config, identifier)
            subtitle_data = load_subtitle_cache(subtitle_cache_path)
            if subtitle_data:
                subtitle_cache_hit = True
                print(f"命中缓存，跳过字幕抓取: {subtitle_cache_path}")
                cached_title = subtitle_data.get("video_info", {}).get("title")
                if cached_title:
                    print(f"缓存视频标题: {cached_title}")

        # 初始化组件（放在缓存检查之后）
        log_step("初始化处理组件")
        extractor = SubtitleExtractor(config)
        summarizer = VideoSummarizer(config)
        
        # 提取字幕（带重试）
        @retry_on_failure(max_retries=config.MAX_RETRY, logger=logger)
        def extract_subtitles_with_retry(url, subtitle_format):
            return extractor.extract_subtitles(url, subtitle_format=subtitle_format)
        
        # 统一规则：subtitle固定输出为srt + md
        effective_subtitle_format = "srt"
        if not subtitle_data:
            log_step("抓取字幕数据")
            subtitle_data = extract_subtitles_with_retry(args.url, effective_subtitle_format)
        if not subtitle_data:
            print("错误: 无法获取视频字幕")
            sys.exit(1)

        if subtitle_cache_path:
            if save_subtitle_cache(subtitle_cache_path, subtitle_data):
                print(f"字幕缓存已更新: {subtitle_cache_path}")
            else:
                print("警告: 字幕缓存保存失败（不影响主流程）")
        
        video_info = subtitle_data.get("video_info", {})
        title = video_info.get("title", "未知标题")
        print(f"成功获取视频字幕: {title}")
        
        # 统一输出命名：summary只保留md；subtitle固定srt+md
        safe_title = identifier if identifier else "".join(
            c for c in title if c.isalnum() or c in (' ', '-', '_')
        ).rstrip()
        safe_title = safe_title[:80]  # 限制长度

        subtitle_srt_default = f"{config.OUTPUT_DIR}/{safe_title}_subtitles.srt"
        subtitle_md_default = f"{config.OUTPUT_DIR}/{safe_title}_subtitles.md"
        summary_md_default = f"{config.OUTPUT_DIR}/{safe_title}_summary.md"

        def ensure_parent_dir(file_path: str):
            parent = os.path.dirname(file_path)
            if parent:
                os.makedirs(parent, exist_ok=True)

        def subtitle_outputs_exist(srt_path: str, md_path: str) -> bool:
            return os.path.exists(srt_path) and os.path.exists(md_path)

        def save_subtitle_pair(srt_path: str, md_path: str) -> bool:
            if subtitle_cache_hit and subtitle_outputs_exist(srt_path, md_path):
                print(f"命中字幕文件缓存，跳过保存: {srt_path} / {md_path}")
                return True
            ensure_parent_dir(srt_path)
            ensure_parent_dir(md_path)
            ok_srt = extractor.save_subtitles_to_file(subtitle_data, srt_path)
            ok_md = extractor.save_subtitles_to_markdown(subtitle_data, md_path)
            if ok_srt:
                print(f"字幕已保存到: {srt_path}")
            else:
                print("错误: 无法保存字幕SRT文件")
            if ok_md:
                print(f"字幕Markdown已保存到: {md_path}")
            else:
                print("错误: 无法保存字幕Markdown文件")
            return ok_srt and ok_md
        
        # JSON模式：只保存JSON
        if args.json:
            log_step("保存JSON字幕文件")
            output_json = args.output if args.output else f"{config.OUTPUT_DIR}/{safe_title}_subtitles.json"
            ensure_parent_dir(output_json)
            if extractor.save_subtitles_to_json(subtitle_data, output_json):
                print(f"字幕已保存到: {output_json}")
                print("处理完成!")
                return
            print("错误: 无法保存字幕JSON文件")
            sys.exit(1)

        # 字幕模式：固定输出srt + md
        if args.no_summary:
            log_step("保存字幕文件（SRT + Markdown）")
            if args.output:
                subtitle_srt_path = args.output if args.output.lower().endswith(".srt") else str(Path(args.output).with_suffix(".srt"))
            else:
                subtitle_srt_path = subtitle_srt_default
            subtitle_md_path = str(Path(subtitle_srt_path).with_suffix(".md"))

            print("保存字幕（SRT + Markdown）...")
            if not save_subtitle_pair(subtitle_srt_path, subtitle_md_path):
                sys.exit(1)
            print("处理完成!")
            return

        # 总结模式：先保存subtitle（srt+md），再保存summary（md）
        subtitle_srt_path = subtitle_srt_default
        subtitle_md_path = subtitle_md_default
        summary_output = args.output if args.output else summary_md_default
        if not summary_output.lower().endswith(".md"):
            summary_output = str(Path(summary_output).with_suffix(".md"))

        # 缓存短路：命中缓存且关键MD都存在时，直接完成
        if subtitle_cache_hit and os.path.exists(subtitle_md_path) and os.path.exists(summary_output):
            log_step("命中总结缓存，跳过字幕保存与总结生成")
            print(f"字幕Markdown已存在: {subtitle_md_path}")
            print(f"总结已保存到: {summary_output}")
            print("处理完成!")
            return

        log_step("保存字幕文件（SRT + Markdown）")
        print("先保存字幕（SRT + Markdown）...")
        if not save_subtitle_pair(subtitle_srt_path, subtitle_md_path):
            sys.exit(1)
        ensure_parent_dir(summary_output)

        if not args.no_summary:
            if not (config.AI_API_KEY or "").strip():
                print("错误: 未提供 AI API Key（可在GUI填写，或在 .env 配置 AI_API_KEY）")
                sys.exit(1)
            log_step("调用大模型生成总结")
            print("正在生成视频总结...")
            summary = summarizer.summarize_video(subtitle_data, args.model)
            
            if summary:
                print("成功生成视频总结")
                
                # 保存总结
                log_step("写入总结Markdown文件")
                if summarizer.save_summary_to_file(summary, subtitle_data, summary_output):
                    print(f"总结已保存到: {summary_output}")
                else:
                    print("错误: 无法保存总结文件")
                    sys.exit(1)
            else:
                print("错误: 无法生成视频总结（请检查 API Key / API地址 / 模型名称）")
                sys.exit(1)
        
        print("处理完成!")
        
    except KeyboardInterrupt:
        print("\n用户中断操作")
        sys.exit(1)
    except Exception as e:
        logger.error(f"发生错误: {e}")
        print(f"发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"发生错误: {e}")
        sys.exit(1)