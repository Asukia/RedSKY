# 霞信 · redsky：朝霞/晚霞邮件提醒

> 朝霞不出门，晚霞行千里。

[English](README.md)

自己部署的朝霞/晚霞提醒。每天到了你设定的当地时间，它会查询下一次日出或日落的
[Sunsethue](https://sunsethue.com/dev-api) 质量预测，**只有分数达到你的阈值才发邮件**，平常不打扰。
Sunsethue 覆盖的地方都能用（南纬 55° 到北纬 70°）。

- 预测：Sunsethue API（质量分 0–1，ICON 模型）
- 辅助：[Open-Meteo](https://open-meteo.com/)（查城市坐标、日出日落时刻、高中低云量；不需要 key）
- 运行：在你自己复制的仓库里用 GitHub Actions 定时运行，不需要服务器和域名。纯 Python 标准库。
- 邮件可选中文或英文。

## 部署步骤

1. **复制一份私有仓库**：点 **Use this template → Create a new repository**，选 **Private**。
   一定要私有：`config.toml` 里有你的邮箱，决策记录 `state/sent.json` 也能看出你的位置。
2. **申请 Sunsethue key**：在 https://sunsethue.com/dev-api 注册，到 portal 生成 key
   （每个账号一个，只显示一次）。免费额度限个人使用。
3. **准备发信邮箱的 SMTP 授权码**：建议专门注册一个用来发信的邮箱。用应用专用密码或授权码，不是登录密码。
   常见设置（以邮箱官方说明为准）：
   - Gmail：`smtp.gmail.com`，端口 465，需要开启两步验证，然后生成"应用专用密码"
   - QQ 邮箱：`smtp.qq.com`，端口 465，在设置里开启 SMTP 后获取授权码
4. **写配置**：先查坐标和时区。可以在本地运行
   ```bash
   python -m glow_alert search-city "Hangzhou"      # 从列表里挑对的那个
   ```
   也可以在浏览器里用 [Open-Meteo 地理编码 API](https://open-meteo.com/en/docs/geocoding-api) 查。
   然后在 GitHub 上打开你的仓库，**Add file → Create new file**，文件名填 `config.toml`，
   粘贴 [`config.example.toml`](config.example.toml) 的内容，填好后提交。中文邮件写 `language = "zh"`。
5. **添加 Secrets**：仓库 Settings → Secrets and variables → Actions → New repository secret，添加
   `SUNSETHUE_API_KEY`、`SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`、`SMTP_PASSWORD`，`MAIL_FROM` 可选。
6. **手动测试**：Actions → glow-alert → Run workflow。
   - 先保持 `dry_run` 和 `ignore_schedule` 都勾选：邮件内容打印在日志里，不发送，也不记录。
   - 再取消 `dry_run`，真的发信。`ignore_schedule` 只跳过"是否到点"的判断，阈值照常生效：
     当天分数不够就收不到邮件。想确保收到一封，可以临时把 `min_quality` 设为 0。
7. 完成。之后每小时自动运行一次，到点就判断。

还没有 `config.toml` 时，定时运行只会留一条警告然后跳过，不会报错。

## 行为说明

- `notify_at` 是订阅时区的当地时间。到点后检查**此后最近的一次**日出/日落：
  早上 08:00 提醒的是当天日落，晚上 21:00 提醒的是次日日出。
- GitHub 的定时任务可能延迟。在 `notify_at` 之后 `grace_hours`（默认 3 小时）内的运行都算数；
  如果运行时事件已经过去，记为 `missed`。
- 每个事件只判断一次。Sunsethue 不可用时（接口报错、额度用完、没有模型数据），
  会发一封标注"降级"的邮件，只附 Open-Meteo 云量。
- 每次判断（发送 / 未达阈值 / 降级 / 错过）都记在 `state/sent.json`，由 workflow 自动提交。
  事后可以对照实际天空，调整自己的阈值。
- 额度：每个事件 5 个 Sunsethue credits，免费版每天 1000 个，个人使用绰绰有余。

## 为什么每小时运行，以及怎么减少运行次数

`.github/workflows/glow-alert.yml` 里的定时（`cron`）用的是 UTC 时间，对所有人都一样；而每个人的 `notify_at`
是自己的当地时间。每小时运行一次，任何时区、任何提醒时间都不用改 workflow，夏令时也不用管；
GitHub 延迟或漏掉一次运行时，下一小时还能补上。

如果想少跑几次，可以改 `cron`，让每次运行都落在 `[notify_at, notify_at + grace_hours)` 这个窗口里。
例如杭州（UTC+8），当地 08:00 和 21:00 提醒，对应 UTC 00:00 和 13:00：

```yaml
    - cron: "17 0,1,13,14 * * *"   # 每个提醒运行一次，再加一小时后的一次备份
```

备份那次不会重复发信，因为每个事件只判断一次。不加备份的话，GitHub 一旦漏跑，当天就收不到提醒。
有夏令时的时区，要确认冬夏两季的运行时间都还在窗口里。私有仓库每月有 Actions 分钟数额度（见 GitHub 计费文档）；
每次运行至少按 1 分钟计，每小时运行一个月大约用 720 分钟。

## 本地运行

```bash
python -m unittest discover -s tests                     # 离线测试
python -m glow_alert run --dry-run --ignore-schedule     # 只打印邮件，不发送（没有 key 时走降级路径）
```

## 致谢与许可证

- 朝晚霞预测来自 [Sunsethue](https://sunsethue.com/)。请使用你自己的 key，并遵守它的条款。
- 天气数据来自 [Open-Meteo.com](https://open-meteo.com/)，以 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
  授权。它的免费 API 仅限非商业使用。
- 代码：[MIT](LICENSE)。

预测仅供参考；本项目没有验证过 Sunsethue 在任何地区的准确率。
