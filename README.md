# Voice Memos → Podcast

一个开源 Codex skill：把 iPhone / iPad 中**指定的语音备忘录**发布到现有 Spotify 节目，并通过同一 RSS 分发到 Apple Podcasts。

An open-source agent skill for publishing selected Voice Memos to a podcast. MIT licensed.

Version: **v2.0.0**. Spotify-only publishing remains the default. A run can optionally share each newly published episode to X and Facebook through Spotify's built-in share buttons.

## 实际工作方式

**选择录音并分享至文件 → 在电脑调用 skill → Spotify for Creators 上传发布 → RSS 更新 → Apple Podcasts 收录。**

已有 Spotify/Anchor 节目优先沿用原节目和 RSS。首次 Apple 提交、账号登录/验证及平台审核仍需完成。平台抓取有延迟；RSS 已更新不代表 Apple 已收录。

这是 agent 技能，不是 iOS App 或后台服务。它无法直接读取手机 App 私有录音库。Spotify 发布使用已登录、支持文件上传的浏览器，由 agent 根据页面操作；不包含未经验证的私有 API 或独立无头上传器。当前仓库包含离线测试，真实账号发布仍需用户指定录音和登录后验证。

## 安装

将本项目 `skills/voice-memos-to-podcast` 文件夹复制到 `~/.codex/skills/`（设置了 CODEX_HOME 时，使用该目录下的 `skills/`）。重新打开会话后调用 `$voice-memos-to-podcast`。

Spotify 模式的准备/验证脚本只需 Python 3.10+ 标准库。上传还需运行环境的浏览器能力和 Spotify 登录。可选自建 RSS 模式另需 FFmpeg、Boto3、Pillow 和用户自己的对象存储，详见技能参考文档。

## 使用示例

Spotify only:

> “Use the Spotify publishing skill. Publish all attached audio files in order.”

Spotify + X + Facebook:

> “Use the Spotify publishing skill. Publish all attached audio files in order and share each successfully published episode to X and Facebook.”

For either mode, each selected file becomes a separate Spotify episode in filename order. In social mode, the sequence for each live episode is Spotify “Episode published!” → X Post → return to Spotify → Facebook Share/Post → return to Spotify → Done → next file. Spotify's prefilled episode link is preferred. Login or security verification may require user action; other normal browser steps proceed without repeated confirmation.

To prepare a folder batch, save the selected Voice Memos as `.m4a` files in one local folder and run:

```sh
python3 skills/voice-memos-to-podcast/scripts/batch.py init \
  --folder '/absolute/path/Voice Memos' --out '/private/path/batch.json'
python3 skills/voice-memos-to-podcast/scripts/batch.py status --ledger '/private/path/batch.json'
```

Add `--mode spotify-x-facebook` to the `init` command for social sharing. The folder scan selects direct `.m4a` files in filename order; it does not include subfolders. Existing explicit M4A, MP3 and WAV paths still work. The agent uploads each selected file through the existing Spotify for Creators workflow; this helper prepares the order and records progress rather than bypassing Spotify's upload UI.

A private batch ledger at `skills/voice-memos-to-podcast/scripts/batch.py` records attempted, confirmed, and failed steps. Resume from it after interruptions. Inspect uncertain posts before retrying, skip completed episodes, and never duplicate a social post. A failed X or Facebook step is recorded so the remaining steps can continue safely. The ledger stays outside Git.

> 用 $voice-memos-to-podcast，把我保存到 Podcast Inbox 的「第十期.m4a」发布到现有节目。RSS 是……；标题……；简介……；无露骨内容；立即公开发布，并检查 Apple Podcasts 的分发状态。

如果还缺必要的元数据，技能会询问；不会根据文件名捏造内容或发布未经指定的录音。选择录音与首次账号配置之后，其余可由具备浏览器能力的 agent 执行。浏览器不可用时提供准备好的文件/元数据供手动上传，并明确说明未发布。

## 内容

- `skills/voice-memos-to-podcast/SKILL.md`：技能入口及发布边界。
- `scripts/release.py`（技能目录内）：准备文件指纹、RSS 基线，验证新增单集，防止重试重复发布。
- `scripts/podcast.py`（技能目录内）：可选的新建 S3 RSS 节目发布器，默认只生成本地预览；不用于现有 Anchor 节目。
- `references/ios.md`：iPhone/iPad 分享步骤及快捷指令配方（不含已签名快捷指令文件）。
- `tests/`：RSS、去重、并发写入保护、失败处理测试。
- `VERSION`, `CHANGELOG.md`, `RELEASE_NOTES.md`：v2.0.0 版本和 GitHub 发布说明。

## 测试

```sh
python3 -m unittest discover -s tests -v
```

测试使用合成数据与模拟存储，不发布真实单集、不访问账号。可选托管测试不要求安装 Boto3；正式运行该模式需安装 `requirements-self-hosted.txt`，并在所选供应商验证条件写入和公开音频访问。

## 隐私与贡献

实际录音、私人配置、RSS 快照和发布回执不提交到开源仓库；也不要提交 Cookie、密码或访问令牌。欢迎通过 issue / pull request 改进已验证的工作流程和测试。平台行为依据链接见技能的 `references/sources.md`。
