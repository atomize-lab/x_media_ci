# x_media/CI 内容存储规范（建议）

目标：让你和其他 agent 可以**按用户名 / 时间 / 标签快速检索**，并且每条推文都能完整落地：**文字 + 图片 + 视频 + 音频 +（可选）博主在该对话下的回复**。

## 目录结构（主存储）

```
x_media/
  CI/
    accounts/
      <handle>/                         # 不含@，例如 b3785486614474
        profile.json                    # 可选：账号信息缓存
        tweets/
          YYYY/
            YYYY-MM/
              <YYYYMMDDThhmmssZ>_<tweet_id>/
                tweet.json              # 主元数据（建议只读、稳定字段）
                media/
                  images/               # 图片（原图优先）
                  video/                # 视频（合成后mp4 + 可选轨道文件）
                  audio/                # 音频（从视频抽取的audio-only mp4 或直接音频）
                  raw/                  # 可选：HLS分片/playlist/调试信息
                replies/
                  author_replies.jsonl  # 可选：博主在该thread下的回复（JSONL）
```

> 说明：  
> - `<handle>` 用于按用户名分组。  
> - `YYYY/YYYY-MM` 便于按时间分片（后续处理大规模数据时更友好）。  
> - `<YYYYMMDDThhmmssZ>_<tweet_id>` 文件夹名同时包含**时间**和**tweet_id**，便于排序与唯一性。

## 索引结构（方便检索/批处理）

```
x_media/CI/
  indices/
    tweets.jsonl                 # 全量索引（每条推文1行JSON）
    by_handle/<handle>.jsonl     # 按账号分片的索引
    by_date/YYYY/YYYY-MM.jsonl   # 按月份分片的索引
```

JSONL（每行一个 JSON）的好处：  
1) 追加写入非常方便；2) agent/脚本可以流式处理；3) 不用担心大文件整体重写。

## tweet.json 建议字段（agent友好）

- `tweet_id`, `tweet_url`, `author_handle`
- `datetime_utc`, `datetime_beijing`
- `text`
- `media[]`：列出每个媒体文件（type/mime/file/sha256/derived_from）
- `components`：可选，记录轨道文件、HLS分片目录等“可复现构建”的材料
- `replies.author_replies[]` 或 `replies/author_replies.jsonl`：存储博主回复（同 handle）

## 关于“图片/视频/音频”

- 图片：优先保存 `pbs.twimg.com/media/...&name=orig` 对应的原图（并在 `media[]` 里记录）。
- 视频：X 常见为 HLS（m3u8 + m4s 分片），建议落地一份**合成后的 mp4**（方便播放/转存），同时保留 `raw/` 里的 playlist 与分片（方便复现/二次处理）。
- 音频：为了便于后续单独处理，建议从 mp4 抽取一份 **audio-only mp4**（本环境 ffmpeg 只保证 mp4 容器）。

# x_media_ci
