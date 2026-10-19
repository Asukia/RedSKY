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

## 收到的邮件

分数达到阈值的那天，你会收到这样一封邮件（示例：时刻是真实数据，分数是演示用的）：

```text
Subject: 霞信｜New York · 今日晚霞「优秀」0.72 · 18:11

New York · 今日晚霞

今日（10月18日 周日）晚霞预测为「优秀」，质量指数 0.72，已达到您设定的提醒阈值 0.41。

　日落时刻　18:11
　黄金时刻　17:56 – 18:26
　蓝调时刻　18:31 – 18:46
　太阳方位　252°（西）
　云　　量　35%（Sunsethue）
　　　　　　低 5% · 中 30% · 高 55%（Open-Meteo）

建议于 17:56 前抵达，面向西方取景。

——
地点：New York（40.7000, -74.0000，America/New_York）
预测：Sunsethue（ICON 模型，0.25° 网格）；云量：Open-Meteo
预测仅供参考，以实际天象为准。
订阅 nyc-sunset · 发送于 2026-10-18 12:17 EDT
```

其他日子不打扰。

## 部署步骤

1. **复制一份私有仓库**：点 **Use this template → Create a new repository**，选 **Private**。
   一定要私有：`config.toml` 里有你的邮箱，决策记录 `state/sent.json` 也能看出你的位置。
2. **申请 Sunsethue key**：在 https://sunsethue.com/dev-api 注册，到 portal 生成 key
   （每个账号一个，只显示一次）。免费额度限个人使用。
3. **准备发信邮箱的 SMTP 授权码**：建议专门注册一个用来发信的邮箱。
   你只需要申请一样东西：给第三方程序用的专用密码（Gmail 叫"应用专用密码"，QQ/163 叫"授权码"），
   不是登录密码。其余几项是每家邮箱固定的设置。以邮箱官方说明为准：

   | 邮箱 | `SMTP_HOST` | `SMTP_PORT` | 要申请的密码 |
   |---|---|---|---|
   | Gmail | `smtp.gmail.com` | `465` | 应用专用密码（先开启两步验证），16 位，填写时去掉空格 |
   | QQ 邮箱 | `smtp.qq.com` | `465` | 授权码（在邮箱设置里开启 SMTP） |
   | 网易 163 | `smtp.163.com` | `465` | 授权码（在邮箱设置里开启 POP3/SMTP） |
   | Outlook / Hotmail | | | 不支持：微软个人账号的 SMTP 只能用 OAuth 登录 |
   | Proton Mail | `smtp.protonmail.ch` | `587` | 只有付费套餐的自定义域名地址可用（SMTP token） |
4. **写配置**：先查坐标和时区。可以在本地运行
   ```bash
   python -m glow_alert search-city "Hangzhou"      # 从列表里挑对的那个
   ```
   也可以在浏览器里用 [Open-Meteo 地理编码 API](https://open-meteo.com/en/docs/geocoding-api) 查。
   想用具体的观景点而不是城市中心，见下面的[精确地点](#精确地点)。
   然后在 GitHub 上打开你的仓库，**Add file → Create new file**，文件名填 `config.toml`，
   粘贴 [`config.example.toml`](config.example.toml) 的内容，填好后提交。中文邮件写 `language = "zh"`。
5. **添加 Secrets**：仓库 Settings → Secrets and variables → Actions → **Secrets** 页签 →
   **New repository secret**，每行添加一项，名字必须一字不差。

   | Secret | 填什么 |
   |---|---|
   | `SUNSETHUE_API_KEY` | 你的 Sunsethue key |
   | `SMTP_HOST`、`SMTP_PORT` | 见第 3 步的表 |
   | `SMTP_USER` | 发信邮箱的完整地址，例如 `you@163.com` |
   | `SMTP_PASSWORD` | 应用专用密码或授权码 |
   | `MAIL_FROM` | 可选，显示的发件人名，例如 `霞信 <you@163.com>`（地址要和 `SMTP_USER` 相同） |

   密钥只放在 Secrets 里，不要贴到 issue、聊天或 `config.toml` 里。
6. **手动测试**：Actions → glow-alert → **Run workflow**。运行结束后点开这次运行，点左侧的 **tick**，
   再展开 **Check forecast and send** 这一步。
   - **先保持 `dry_run` 和 `ignore_schedule` 都勾选**。不会发信，也不记录。每条订阅会有一行结果，
     例如 `INFO my-sunset: sunset 2026-10-19 -> below_threshold (q=0.05)`：
     - `alert`：分数达到阈值，下面会打印出将要发送的邮件。
     - `below_threshold`：这次不发信。这是正常情况，大多数日子都是这样。
     - `degraded (原因)`：没拿到预测。如果原因是 `SUNSETHUE_API_KEY not set`，说明这个 Secret 没加或名字不对；
       这一步的 `env:` 里，读到的 Secret 显示为 `***`，没读到的是空的。
   - 想不管分数先看看邮件长什么样，就在 `config.toml` 里临时把 `min_quality` 设为 `0`。
   - **再取消 `dry_run`**（`ignore_schedule` 保持勾选），真的发一封。日志里出现 `mailed 1 recipient(s)` 就是发出去了；
     第一次记得看看垃圾邮件。
   - 测完把 `min_quality` 改回去，而且要在下一次定时运行之前，否则那次运行会不管分数直接发信。
7. 完成。之后每小时自动运行一次，到点就判断。

还没有 `config.toml` 时，定时运行只会留一条警告然后跳过，不会报错。

## 精确地点

`latitude` / `longitude` 可以是任意一点，不一定是城市中心，填你实际去看霞的地方就行。

1. 在 Google 地图上**右键点那个位置**，菜单第一行就是坐标（例如 `35.62700, 139.77600`），点一下即可复制。
   OpenStreetMap 上右键 →"显示地址"也能看到坐标。
2. 第一个数填 `latitude`，第二个数填 `longitude`。保留 5 位小数（约 1 米）就够了。
3. 查这个点的时区：在浏览器打开
   `https://api.open-meteo.com/v1/forecast?latitude=<纬度>&longitude=<经度>&timezone=auto`，看 `"timezone"` 那一项。
4. 可以设好几个地点：每个地点、每种事件各写一条 `[[subscription]]`，`id` 不能重复。

找具体地点别用 `search-city`：它只认到城市和区一级，街区名可能搜到别处的同名地方
（搜 "Odaiba" 得到的是北海道的一个地方，不是东京的台场）。

精确地点能改变什么、不能改变什么：
- **不变**：同一座城市里，质量分很可能是一样的。Sunsethue 的模型网格是 0.25°（在东京约 28 × 23 公里一格），
  相距几公里的点通常落在同一格。这是按网格大小推断的，Sunsethue 会不会在格点之间插值，没有核实过。
- **会变**：日出日落时刻、太阳方位和 Open-Meteo 云量都按你那个点计算，邮件里写的也是你真正要去的地方。
- **任何预测都不管**：那个点朝西（晚霞）或朝东（朝霞）有没有楼、山或树挡着。这取决于你选的地方。

## 行为说明

- `notify_at` 是订阅时区的当地时间。到点后检查**此后最近的一次**日出/日落：
  早上 08:00 提醒的是当天日落，晚上 21:00 提醒的是次日日出。
- GitHub 的定时任务可能延迟。在 `notify_at` 之后 `grace_hours`（默认 3 小时）内的运行都算数；
  如果运行时事件已经过去，记为 `missed`。
- 每个事件只判断一次。Sunsethue 不可用时（接口报错、额度用完、没有模型数据），
  会发一封注明"暂无预测"的邮件，只附 Open-Meteo 云量。
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
