# 维雾主义

中文维基目录猜词游戏。当前目录是**独立服务器迁移版**：Next.js / Node.js / PostgreSQL。

**请先阅读 [DEPLOY.md](DEPLOY.md)**，其中明确说明完整线上数据库导出尚未获得、快照导入限制和正式上线前的核验步骤。

以下是原有功能设计说明，部分 Cloudflare Workers / D1 开发部署说明仅作历史参考。

## 用户与玩法

- 游客只可玩每日题（含已上线历史题）；独立用户名密码注册，图片验证码、服务端限频；不提供改密或找回。
- 用户可玩每日题、随机挑战、大海捞针、精选题库；成绩以服务端开题、判题、完成时间为准，跨设备共享。
- 用户资料、评论、评价、别名申诉均持久化。评论与简介仅在自己完成或揭晓后可见。
- 管理员可搜索玩家、查看网站统计、禁用昵称/头像、安排未来七天每日题、管理词条与黑名单、审核别名、隐藏评论。
- 唯一超级管理员由服务端部署配置预置；没有申请或认领入口，普通注册永远只能建立普通用户。只有此账号能授予/撤销管理员。
- 每题六次猜测。排行榜统计每用户每词条首次完成；成功率榜须完成至少20个不同词条。每日速度榜排除已接触词条的玩家和游客导入成绩。

## 数据与筛选

文章主键是中文维基的官方 pageid（整数），revision 用于追溯快照。每次游戏保存开题快照，后续文章变化不影响当前题目。文章内容按需入库，官方范围只分批索引标题。

启动快照 data/seed.json 来自真实维基 API，包含正文字符统计、简介、目录、分类和近30日浏览量中位数；旧 data/wiki.json 保留原版数据。当前启动快照16篇，默认规则下12篇可用。数据采集脚本对未能成功抓取的数据不伪造、不补零。

默认统一筛选：正文纯文本去空白至少800字符；排除参考/附录后必须有一级目录包含二级目录；标题/分类命中敏感词跳过；近30日每日 user 浏览量中位数至少3；管理员黑名单优先。维基 info.length 是字节数，不作为字数。自动排除记录持久化；网络错误或浏览量缺失只暂缓，不永久拉黑。敏感关键词不能保证覆盖所有政治敏感内容，需人工审核补充。

默认自动精选：至少10人评价且好评率>=80%；管理员手选为固定精选，自动精选会随比例降低退出。阈值可在后台修改。昵称/头像封禁隐藏当前值、要求修改，并拒绝直接恢复被封禁值。

随机范围：二至五级基础条目、典范、优良、维基志异；来源入口及分页进度保存在 source_jobs。source-seed.json 仅含首批标题/子页面索引。大海捞针使用中文维基随机主命名空间，仍经过统一筛选。外部接口限流时返回可重试错误；不会用别的范围冒充结果。

## 运维

- D1 绑定 DB；SUPER_ADMIN_ID、SUPER_ADMIN_USERNAME、SUPER_ADMIN_SALT、SUPER_ADMIN_HASH 由 Sites 部署环境配置。密码只保存独立盐与哈希，明文不写入源代码。
- 图片验证码一次性、5分钟有效；密码 PBKDF2-SHA256 独立随机盐；会话令牌散列入库，HttpOnly/SameSite cookie；写接口验证 Origin。
- app/api/v1/route.ts 为统一接口，lib/server/service.ts 执行业务与权限；旧 /api/puzzle 已关闭，不能绕过记录直接揭晓。
- `GET /api/v1?action=init` 会幂等补齐今天+未来7天的排期，并返回 scheduledThrough，既用于进入页面也可由每日云任务调用。不会覆盖已安排日期或泄露未来题目。当天和历史题不可改。
- 自动运行时：用 Sites get_site 获取当前网址及服务访问凭据；私有站点携带其返回的 OAI-Sites-Authorization bearer（仅发往该站，不保存或输出）；调用 init 并确认 scheduledThrough >= 北京日期+7天。公开站点可匿名调用 init。若服务凭据不可用，不绕过访问控制，报告本次未运行；下一位访客进入仍会补齐。
- 索引可从后台逐批同步；新增题目在随机抽取时抓取。单次插入索引最多50条一批。
- 每次部署自动应用追加的 Drizzle schema migration；数据迁移与种子数据分离。禁止更改已部署迁移文件。
- 本地旧版浏览器 localStorage 记录不会冒充可信服务器成绩导入。新版本游客当日成绩可在注册/登录后迁入，但不进入速度榜。

## 验证

`npx tsc --noEmit`

`node --import tsx scripts/test-server.mts`

`node /home/agent/.codex/plugins/cache/openai-curated-remote/sites/1.1.6/scripts/build-site.mjs`

服务端测试使用真实 SQLite 执行生成迁移和业务 SQL，覆盖权限、会话、验证码、开题、计时、判题、别名、评价、审核、统计和跨站写入拒绝。浏览器验证了游客开题、遮字、正确答案、揭晓简介/评论、刷新恢复成绩和警告页面。独立登录的生产 Cookie、外部实时维基抽题还须在部署环境验证。

目录与简介由中文维基百科贡献者提供，CC BY-SA 4.0；揭晓后链接原条目，历史可追溯贡献者；目录仅作遮字处理。

随机范围为单选。进行中的随机题将范围写入 games.source；前后端同时锁定，刷新、跨设备和直接请求都不能换范围。完成或揭晓后解锁。

## 2026-11-18 更新

- 当前地址 https://wiki-mystery-tfh.achromakui.chatgpt.site 。每日排期任务动态读取 get_site，不依赖旧域名。
- dailyState 仅读取已有作答，不开题、不启动计时；进入每日一题自动恢复。分享文本不含答案，包含日期、结果、猜测次数、用时和当前站点地址。
- 完成后返回原始目录；未完成只返回遮字目录。前三次错误分别解锁字符数（不含末尾括号消歧义）、领域、首字，服务端限制提示级别。
- 标题末尾的中文/英文括号消歧义可省略作答。随机题的 source 随游戏保存，玩家和管理员记录可查询；旧的缺失分类不会猜测补写。
- 不存在/移动/简繁名称先 query 解析 pageid，再 parse；内部数字标题与 ID 分开。selection_skips 缓存无效名称和暂缺浏览量的候选，正常页面仍用官方 pageid。临时网络错误不永久排除。
- 随机筛题每批最多22秒，候选不合格静默返回 pending，客户端自动续取下一批；可取消。服务断连或范围耗尽才显示普通服务状态，不泄露筛选原因。
- 新增第 N 届类条目筛选，适用于缓存与新抓取。管理员解除时清理相应标题缓存，再重新核验。
- 评论、答题记录、玩家、词条、审核、管理日志和总榜每页20条；每日速度榜维持前10。列表支持对应搜索/分类。每日历史使用日期选择器。
- 词条管理含全部、点赞、点踩、屏蔽四个页签，展示领域、已记录题库来源、赞踩数和原文链接；可直接加入精选/屏蔽。


## Official categories and answer resolution

The eight navigation groups and their child topics follow `Wikipedia:分類索引` / `Template:Category` revision 86710543. They are not mutually exclusive category roots. The four article-only links in that template (南极洲、中国画、生肖、神学) use verified, existing same-name categories for topic selection. `lib/topics.ts` retains the canonical Category links. Classification follows non-hidden official category edges, caches them for 30 days, and stores the verified paths in `article_topics`. Bounded unresolved searches show 待归类 and can be continued from the admin page. Topic pools traverse Categorymembers with durable continuations and a cycle-safe queue; random draws use the portion indexed so far, not a uniform sample of the entire Wikipedia graph.

Official answer resolution follows redirects and Chinese title conversion to the final main-namespace page ID. Disambiguation responses request a qualified answer without consuming a guess. A link on a disambiguation page is not treated as an alias. Full titles, approved aliases, and the explicitly requested parenthesis-free base name remain accepted. Hints are category, character count, first character.

## Pending: complete monthly snapshot replacement

The live application still fetches article content from the official APIs. It does NOT claim to have imported a full snapshot, and no nonfunctional update button is exposed. The 2026-11-01 multistream archive is about 3.64 GB compressed. A persistent import worker and storage for the parsed corpus must be provisioned before implementing the requested superadmin update. The current Sites manifest supplies one D1 database and no queue/compute service; a request-scoped 128 MB Worker is not a full-snapshot job runner.

Required integration: a long-running service accessible through HTTPS with server-held credentials. The superadmin-only update endpoint should enqueue an idempotent import; the service resolves the latest completed dated dump, checks the published checksum, streams decompression and parsing, imports page IDs/redirects/disambiguation/category links/TOCs into a staged dataset, and checkpoints progress. Activate the new dataset atomically only after completeness and integrity validation. Keep user records, moderation and manual daily assignments in the existing app database. XML wikitext alone does not include pageview statistics or template-expanded TOCs; rendered template handling and a separate official pageview feed remain necessary.


## Recognition radar

Profile and administrator player views share eight official axes. A score is the percentage of successful first completed encounters per article and category; revealed/exhausted attempts count as failures. Ongoing attempts and unclassified articles are excluded. Membership in multiple second-level topics of one group is deduplicated; an article in multiple top-level groups counts once in each. Only axes with zero completed articles score zero by default. Every nonempty axis uses its observed success rate, even with one sample. Counts below five are marked as sparse for context without changing the score. No time/guess-count weighting is used, and all modes are included. Topic challenge hints skip category: first wrong answer reveals length, second reveals first character, later wrong answers add no new hint.

## 精选管理

后台“精选管理”支持按名称或 pageid 新增、分页搜索、官方一二级分类及可用状态筛选、目录和简介预览、维基链接、移出和重新加入、自动精选转人工精选。页面显示赞踩数、好评率和入选方式。管理员移除只影响精选池，不屏蔽词条或删除答题记录；已屏蔽条目也可以直接移出。移除后不会被后续投票重新自动加入，可由管理员明确恢复。所有精选调整记录在操作日志中。

`articles.featured` 状态：-1 人工移除、0 普通、1 人工精选、2 自动精选。精选抽题包含 1 和 2，并继续遵守统一筛选和跳过已答规则；自动评价仅更新 0 和 2。无需数据库迁移。首页玩法顺序为每日一题、精选题库、随机挑战、大海捞针。
