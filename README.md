# B站视频字幕获取与总结工具

从B站视频获取AI字幕并生成内容总结的Python工具。

## 功能

- 获取B站视频AI字幕（含CC字幕）
- 使用AI模型生成视频内容总结
- 支持命令行和图形界面

## 安装

```bash
pip install -r requirements.txt
```

## 配置（重要）

### 1. 复制配置文件

```bash
cp .env.example .env
```

### 2. 配置B站Cookie（最简）

只需要一种方式，二选一：

- **方式A（推荐）**：在 `.env` 写入整段请求头  
  `BILIBILI_COOKIE=...`
- **方式B**：把浏览器导出的 Cookie JSON 存为 `key.json`（或在 `.env` 指定 `BILIBILI_COOKIE_FILE=你的文件`）

最小必需键（核心）：`SESSDATA`  
建议同时包含：`bili_jct`、`DedeUserID`（通常整段 Cookie 自然会包含）

### 3. 配置AI总结API（可选，用于生成总结）

```
AI_API_KEY=your_api_key_here
AI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
DEFAULT_MODEL=GLM-4.7
```

说明：`/api/coding/paas/v4` 仅适合 Coding 场景，通用视频总结建议使用通用端点 `/api/paas/v4`。

## 使用

### 命令行

```bash
# 基本用法
python main.py -u "https://www.bilibili.com/video/BV1GJ411x7h7"

# 只获取字幕，不生成总结
python main.py -u "视频URL" --no-summary

# 只获取字幕并导出为SRT/VTT/LRC
python main.py -u "视频URL" --no-summary --subtitle-format srt
python main.py -u "视频URL" --no-summary --subtitle-format vtt
python main.py -u "视频URL" --no-summary --subtitle-format lrc

# 保存为JSON格式
python main.py -u "视频URL" --json

# 指定输出路径和AI模型
python main.py -u "视频URL" -o "output.md" -m "GLM-4.7"
```

### 图形界面

```bash
python gui.py
```

### Windows批处理

```bash
run.bat
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `-u, --url` | B站视频URL（必需） |
| `-o, --output` | 输出文件路径（可选） |
| `-m, --model` | AI模型（默认`GLM-4.7`） |
| `-v, --verbose` | 详细输出模式 |
| `--no-summary` | 不生成总结，只获取字幕 |
| `--json` | 保存为JSON格式 |
| `--subtitle-format` | 字幕导出格式：`txt`/`srt`/`vtt`/`lrc`（默认`txt`） |

## 项目结构

```
videosummary/
├── main.py                 # 命令行入口
├── gui.py                  # 图形界面
├── bilibili_api.py         # B站API（核心）
├── subtitle_extractor.py   # 字幕提取
├── video_summarizer.py     # 视频总结
├── error_handlers.py       # 错误处理
├── utils.py                # 工具函数
├── requirements.txt        # 依赖
├── .env.example            # 配置示例
└── output/                 # 输出目录
```

## API端点

- 视频信息：`https://api.bilibili.com/x/web-interface/view`
- 字幕信息：`https://api.bilibili.com/x/player/wbi/v2`
- 字幕下载：`https://aisubtitle.hdslb.com/bfs/ai_subtitle/...`

## 常见问题

### 无法获取AI字幕

1. 确认 Cookie 中包含 `SESSDATA`（或直接使用完整 `BILIBILI_COOKIE`）
2. 确认视频确实有AI字幕（播放器中能看到字幕按钮）
3. 使用 `-v` 参数查看详细日志

### 总结生成失败

1. 检查是否配置了 `AI_API_KEY`
2. 使用 `--no-summary` 参数只获取字幕

## 注意事项

- 遵守B站使用条款和相关法律法规
- 本工具仅用于学习和研究目的

## 许可证

MIT License
