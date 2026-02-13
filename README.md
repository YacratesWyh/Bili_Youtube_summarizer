# 视频字幕与总结工具

获取b站ai字幕。油管字幕建设中……
需要b站大会员cookie。

```text
output/
  BV1RLqdBgEPN_subtitles.srt
  BV1RLqdBgEPN_subtitles.md
  BV1RLqdBgEPN_summary.md
```

字幕是 `srt + md` 两份；开启自动总结会再多一个 `summary.md`。

## 30 秒上手

```bash
pip install -r requirements.txt
cp .env.example .env
python gui.py
```

## 配置 `.env`（最小）

```env
AI_API_KEY=你的模型Key
AI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
DEFAULT_MODEL=GLM-4.7
BILIBILI_COOKIE_FILE=key.json
```

- 只获取字幕：`AI_API_KEY` 可空
- 自动总结：`AI_API_KEY` 必填

## 准备 `key.json`（重点）

`key.json` 是通过 **Cookie-Editor** 导出的 B 站 cookies JSON。

步骤：
1. 浏览器登录 B 站
2. 打开 Cookie-Editor
3. 选择 `bilibili.com`，点击 Export JSON
4. 保存为项目根目录 `key.json`

只要文件里包含有效登录态（通常包含 `SESSDATA`），即可抓字幕。

## 运行

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

## 缓存说明

- 命中字幕缓存时会跳过重复抓取
- 命中缓存且目标文件已存在时会跳过重复写入
- 命中缓存且 `subtitles.md + summary.md` 都存在时，会直接走“总结已完成”路径
