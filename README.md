<!--
 * @Author: cyanocitta
 * @Date: 2026-02-13 11:40:13
 * @LastEditTime: 2026-02-13 17:34:59
 * @FilePath: \videosummary\README.md
 * @Description: 
-->
# 视频字幕与总结工具（最简说明）

目标：输入 Bilibili/YouTube 视频 URL，导出字幕；可选生成总结（这里使用glm，也应该兼容openai）。需要b站大会员cookie。

## 1) 安装

```bash
pip install -r requirements.txt
```

## 2) 配置 `.env`（可选）

复制模板：

```bash
cp .env.example .env
```

Windows 也可以直接新建 `.env`，填下面这些：

```env
# 总结功能（可选）
AI_API_KEY=你的模型Key
AI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
DEFAULT_MODEL=GLM-4.7

# Cookie 文件路径（推荐）
BILIBILI_COOKIE_FILE=key.json
```

说明：
- 只想“获取字幕”，`AI_API_KEY` 可不填。
- 想“自动总结”，`AI_API_KEY` 必填。

## 3) 准备 `key.json`（重点）

`key.json` 是 **Cookie-Editor 导出的 cookies JSON**。

最短流程：
1. 浏览器登录 B 站。
2. 打开 Cookie-Editor 扩展。
3. 对 `bilibili.com` 执行导出（Export JSON）。
4. 保存为项目根目录 `key.json`。

只要文件里包含有效登录态（通常有 `SESSDATA`），程序就能用。

## 4) 运行

### GUI

```bash
python gui.py
```

### 命令行

```bash
# 自动总结
python main.py -u "https://www.bilibili.com/video/BVxxxx"

# 仅获取字幕
python main.py -u "https://www.bilibili.com/video/BVxxxx" --no-summary
```

## 5) 输出结果

- 字幕模式：`*_subtitles.srt` + `*_subtitles.md`
- 总结模式：在以上基础上再输出 `*_summary.md`

如果命中缓存且文件已存在，会跳过重复抓取与重复写入。
