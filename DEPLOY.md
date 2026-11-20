# 维雾主义 · 自有服务器部署与维基百科题库迁移指南

> **交付状态说明（重要）**
>
> 本包包含经过独立 Next.js 构建验证的应用源码、PostgreSQL 结构、完整 D1/SQLite 数据导入转换程序、中文维基百科**本地快照校验/解析/题库替换程序**和定时任务模板。快照由你手动下载，不需要服务器访问维基百科下载站。
> **不包含现有 ChatGPT Sites 线上数据库的完整玩家数据**。当前 Sites 只提供分页读取，长词条 JSON 和历史游戏快照会被截断；不能把这种读取结果当作可靠备份。必须先经授权取得完整 D1 SQL/SQLite 导出，再运行转换工具。没有完成这一步，请勿切换生产域名。
> 此版本的编译已验证；但未连接你的生产 PostgreSQL，也未运行整份约 3.6 GB 的中文维基快照。首次上线必须按本指南做测试和数据核对。

## 1. 环境与目录

- 建议 Ubuntu 22.04/24.04、4 核 CPU、至少 8 GB RAM（全量导入更舒适）、至少 100 GB SSD；日常网站本身要求低于导入任务。
- Docker Engine + Docker Compose 插件；已经存在的 PostgreSQL 16 或较新版本。
- `python3`、`python3-venv`、`sqlite3`、PostgreSQL 客户端 `psql`（用于执行 SQL）。
- 快照由你在个人电脑下载后传到服务器，因此服务器不需要访问 `dumps.wikimedia.org`；但网站运行时获取热度数据等在线功能仍可能需要外部 API 网络访问。
- DNS 域名及 HTTPS 反向代理（Caddy 或 Nginx）。不建议对公网开放 PostgreSQL 端口。

源码不是原封不动的 Cloudflare Worker 包：`app/api/v1/route.ts` 已切换到 Node.js/PostgreSQL，原有账号密码散列兼容保留。用户从 Sites 域名换到新域名后需重新登录。

## 2. 新建数据库

在已有的 PostgreSQL 实例中创建专用用户和数据库，赋予该数据库的完整表级权限。

示意（`psql` 的超级用户会话中执行；请替换密码）：

```sql
CREATE ROLE weiwu LOGIN PASSWORD '请自行生成强密码';
CREATE DATABASE weiwu OWNER weiwu ENCODING 'UTF8';
```

用可连接数据库的宿主机/管理终端执行：

```bash
psql "postgresql://weiwu:密码@127.0.0.1:5432/weiwu" \
  -v ON_ERROR_STOP=1 -f postgres/01_schema.sql
```

**注意：** `host.docker.internal` 仅是容器内到宿主机的别名。宿主机上的 `psql` 不一定能使用它；应填真实数据库地址。

## 3. 迁移原网站数据（不可跳过）

需要 Sites 当前线上 D1 的**完整导出**。如果 D1 归属你可直接管理的 Cloudflare 账号，可以参考 Cloudflare 官方 `wrangler d1 export ... --remote --output=legacy-d1.sql`。ChatGPT Sites 管理的 D1 不一定可被个人 Cloudflare token 直接访问；可能需通过临时受保护的站点导出功能，具体必须先获得 Site 所有者授权、配置访问控制并审核后才部署。

得到完整 `legacy-d1.sql` 后，在**私有的安全主机**上导入成 SQLite：

```bash
sqlite3 legacy.sqlite3 ".read legacy-d1.sql"
python3 scripts/d1_to_postgres.py --sqlite legacy.sqlite3 --output postgres/02_data.sql
```

若已取得完整 `legacy.sqlite3`，可跳过第一行。使用 `psql` 导入 PostgreSQL：

```bash
psql "postgresql://weiwu:密码@127.0.0.1:5432/weiwu" \
  -v ON_ERROR_STOP=1 -f postgres/02_data.sql
```

`02_data.sql` 含用户名、密码哈希和玩家历史，属于敏感备份：权限设置为 `0600`、不要放到网站 `public/`、不要提交 Git、不要公开分享，迁移成功并保留加密离线备份后清理临时明文。

转换工具逐表导出原站 22 张业务表，支持长 JSON，不会故意截断历史快照。导入后应对比新旧库的 `users`、`games`、`guesses`、`articles`、`comments`、`daily`、`aliases` 等表总行数，抽样检查较长的 `games.snapshot` 和 `articles.data`，并模拟真实玩家登录。

如果旧数据尚未取得，仍可先创建全新数据库、测试网站和快照工具，但**不能视为已完成玩家迁移**。

## 4. 部署 Node.js 网站

```bash
cp .env.example .env
chmod 600 .env
```

在 `.env` 中配置真实 `DATABASE_URL`。默认 Compose 将应用绑定到宿主机 `127.0.0.1:3000`，不会自动直接暴露公网；配置反向代理将 HTTPS 请求转发到这里。
配置正式 HTTPS 域名后，将 `.env` 中 `PUBLIC_ORIGIN` 设为完整原点，例如 `https://wiki.example.com`，不能带路径或结尾斜杠。附有 `Caddyfile.example` 供修改。

```bash
docker compose up -d --build
docker compose logs -f --tail=100 weiwu
```

在服务器本机测试：

```bash
curl --fail 'http://127.0.0.1:3000/api/v1?action=init'
```

**反向代理要求：** 保留正确的 `Host` 和 HTTPS 协议信息，设置可信 `X-Real-IP`；对外清除客户自己发送的同名头，不要让访客绕过限流。API 的 POST 会校验 `Origin` 与请求 URL 同源。数据库只在内部网络开放。

如果使用全新空库而非迁移玩家，需初始化管理员（脚本会交互询问账号与密码，不回显密码）：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-snapshot.txt
export DATABASE_URL='postgresql://weiwu:密码@127.0.0.1:5432/weiwu'
.venv/bin/python scripts/bootstrap_admin.py
```

如果已有迁移的管理员账号，不要运行这个脚本；原密码哈希格式兼容，可用旧账号登录。

## 5. 手动下载并放置官方中文维基百科快照

应用只保存词条标题、摘要、目录、分类、别名、修订信息等必要字段；**不保存完整正文或图片**。

官方目录：<https://dumps.wikimedia.org/zhwiki/latest/>。你只需要从**同一次快照**下载以下原始文件：

1. `zhwiki-latest-pages-articles-multistream.xml.bz2`（2026-11 约 3.64 GB）——从 XML 提取标题、目录、重定向和导言摘要，原始正文只用于解析、不会写入题库。
2. `zhwiki-latest-categorylinks.sql.gz`（约 265 MB）——官方分类连接关系。
3. `zhwiki-latest-md5sums.txt`（约 21 KB）——用于本地核验转储文件是否完整、同批次。**注意：清单内通常写的是 `zhwiki-20261101-*` 这样的日期文件名；程序会自动对应你下载的 `zhwiki-latest-*`，并核对月份。**
4. 使用 `cl_target_id` 的分类转储（包括 2026-11）还需同次快照的 `zhwiki-YYYYMMDD-linktarget.sql.gz`，用来将分类目标 ID 还原为分类名。也支持对应的 `zhwiki-latest-linktarget.sql.gz`。

不需要 `pages-meta-history`、完整历史、图片或 multistream 的 `index.txt`；摘要快照已停止提供，摘要从 XML 的导言提取。下载后**不要解压，也不要改文件名**。

在服务器将文件放到以下位置（如果实际运行用户不是 `weiwu`，请用该用户能读写的目录及权限）：

```text
/var/lib/weiwu/wiki-dumps/
  2026-11/
    zhwiki-latest-pages-articles-multistream.xml.bz2
    zhwiki-latest-categorylinks.sql.gz
    zhwiki-20261101-linktarget.sql.gz
    zhwiki-latest-md5sums.txt
```

可用 WinSCP/SFTP 上传。下一月就在同一个父目录新建 `2026-12`，**不要覆盖上个月文件**。名称里的 `latest` 是官网下载时的文件名，月份由其外层文件夹标识；务必在官网下载文件轮换前取齐所需文件，否则校验失败。

文件放好后，先验证而不连接数据库（校验 3.9 GB 文件可能耗时数分钟）：

```bash
.venv/bin/python scripts/wiki_snapshot.py check --directory /var/lib/weiwu/wiki-dumps/2026-11
```

各转储文件均出现 `Verified local` 后，才进行解析。程序不会自动下载或补齐任何缺失文件。服务器需预留足够的磁盘空间用于压缩包、临时分类缓存和 PostgreSQL 数据；建议至少 100 GB 可用空间。

已启用的快照若因旧版导入器丢失原始分类，在配置好同一数据库的 `DATABASE_URL` 后，可以单独回填。此命令会重新读取完整转储并创建临时 SQLite 索引，只处理该快照中原始分类为空且没有分类记录的词条。成功匹配且原状态为 `unclassified` 的词条恢复为 `pending_views`。

```bash
.venv/bin/python scripts/wiki_snapshot.py repair-categories --directory /var/lib/weiwu/wiki-dumps/2026-11 --snapshot 2026-11
```

建议先测试导入小样本；在测试库中运行：

```bash
export DATABASE_URL='postgresql://weiwu:密码@127.0.0.1:5432/weiwu'
.venv/bin/python scripts/wiki_snapshot.py stage --directory /var/lib/weiwu/wiki-dumps/2026-11 --snapshot 2026-11 --max-pages 100
.venv/bin/python scripts/wiki_snapshot.py classify --directory /var/lib/weiwu/wiki-dumps/2026-11 --snapshot 2026-11
```

`--max-pages` **只用于测试**，绝对不能把小样本激活到生产题库。确认程序能够处理你的环境后，重新运行不带该参数的 `stage` 和 `classify`：

```bash
.venv/bin/python scripts/wiki_snapshot.py stage --directory /var/lib/weiwu/wiki-dumps/2026-11 --snapshot 2026-11
.venv/bin/python scripts/wiki_snapshot.py classify --directory /var/lib/weiwu/wiki-dumps/2026-11 --snapshot 2026-11 --max-depth 7
```

解析结果先写入 `wiki_stage_articles` / `wiki_stage_topics`，不会覆盖当前线上 `articles`。分类关系由快照中的官方 `categorylinks` 展开至多七层，无法归类的词条不进入随机池。

确认数量和随机样本合理后，**再执行有保护的切换**：

```bash
.venv/bin/python scripts/wiki_snapshot.py activate --snapshot 2026-11 --confirm 2026-11
```

切换会保留原 `users`、`games`、`guesses`、`votes`、`comments`、`daily`、`exclusions`、`settings`、`aliases`，并尽量保留被玩家历史引用、每日题目引用和被管理员精选的旧词条。旧 `articles` 表归档为 `wiki_articles_before_2026_11`，用于回退，不会立刻删除。

### 目录、摘要和热度的重要限制

- 离线 Wikitext 解析对模板嵌入目录的支持不等同于 MediaWiki 官方渲染器。精选题及上线前抽样需与中文维基页面的实际目录核对；复杂词条应通过官方解析 API 再校验。
- 摘要来自导言 Wikitext 清理，最多约 600 字符，不是生成式 AI 摘要。
- **快照不含最近 30 天浏览量**。新词条先处于 `pending_views`，首次候选时由服务端获取 Wikimedia 浏览量并应用原热度规则；校验通过后变为 `active`。这会让未预热的随机题首次响应较慢，需要生产前预热已选题库。
- WikiRank 评分也不在官方正文快照里，继续作为独立可选数据来源。
- 保留正确归属：使用 Wikipedia 文字时显示相应的词条原文链接、许可说明与来源，并按 CC BY-SA 4.0 条款处理再利用内容。

## 6. 每月本地识别、解析与替换（不联网下载）

`wiki_snapshot.py auto` 现在只扫描 `/var/lib/weiwu/wiki-dumps` 下的 `YYYY-MM` 目录，选择最新月份，检测是否已经处理。未处理且文件齐全时，自动校验 MD5、解析 XML、生成分类并准备切换；**不会请求维基下载站**：

```bash
.venv/bin/python scripts/wiki_snapshot.py auto --directory /var/lib/weiwu/wiki-dumps
```

默认只准备，不自动切换。**明确添加 `--activate`** 后，才会在词条数至少 10,000 且分类完成等保护条件满足后替换线上题库：

```bash
.venv/bin/python scripts/wiki_snapshot.py auto --directory /var/lib/weiwu/wiki-dumps --activate
```

包内的 `systemd/weiwu-wiki-snapshot.service` **默认带 `--activate`**：每天凌晨 3 点扫描是否放入了新月份快照，检测到完整新数据就自动解析、分类和切换；若同月份已启用，则几乎不消耗额外资源。首次完整验证之前，请先手动按第 5 节演练；如果希望每次都由你确认切换，部署计时器前把 service 中的 `--activate` 删除。缺少任何文件、校验不通过或导入数不足时不会切换。

示例 systemd 服务与计时器位于 `systemd/`；启用前核对路径、运行账户、目录写权限和 `.env`：

```bash
sudo cp systemd/weiwu-wiki-snapshot.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now weiwu-wiki-snapshot.timer
sudo systemctl list-timers weiwu-wiki-snapshot.timer
```

服务按服务器时区每天凌晨 3 点检查一次；它只处理你手工上传到新月份目录的文件。如需上传后立刻执行，可手动运行 `sudo systemctl start weiwu-wiki-snapshot.service`。保留旧归档表直到确认题库、历史、排行、每日计划和分类统计正常，再由管理员单独清理。

## 7. 正式切换前的验收清单

- [ ] 当前 Sites 原库已获得**完整、不截断**的 SQL/SQLite 备份，行数与校验正确。
- [ ] PostgreSQL 数据成功导入且玩家能以原用户名/密码登录。
- [ ] 猜词逻辑、目录提示、结束揭晓、精选、过滤、专题、雷达图与排行榜经过实际访问测试。
- [ ] 快照已人工下载、同月文件校验成功，解析、分类、切换、回退演练已在测试库通过。
- [ ] 已确认目录抽样质量；已预热所需词条的浏览量。
- [ ] 每日题目排期自动化已改在你的服务器执行；旧 Sites 云端日更任务准备在切换时停用。
- [ ] Nginx/Caddy 证书有效，数据库与后台未对公网裸露，备份恢复已演练。
- [ ] 最终短暂停止旧站写入 → 重新备份最后增量 → 导入 → 核对 → 切换 DNS。

## 8. 更新、备份与故障处理

应用更新只需保留 `.env` 和 PostgreSQL 数据，更新代码后 `docker compose up -d --build`。正式更新前用 `pg_dump -Fc` 做数据库备份，并在另一数据库演练恢复。`wiki_articles_before_YYYY_MM` 是单独的词条回退表，不是整个 PostgreSQL 备份；不能取代数据库备份。

不要在完成完整导出和验收前删除或停用 ChatGPT Sites 旧站。只有确认新站稳定后，才停掉旧站排期任务，以免产生两套日题。
