---
title: 长时运行应用开发的 harness 设计
source_url: https://www.anthropic.com/engineering/harness-design-long-running-apps
source_domain: anthropic.com
published_date: '2026-03-24'
added_date: '2026-07-16'
slug: anthropic-com-20260324-long-running-harness-design
summary: Anthropic 提出面向长时程应用开发的规划器、生成器与评估器三智能体 harness，以上下文重置、结构化交接、独立评估和迭代反馈提升自主编码与前端设计质量。
tags:
- AI agents
- agent harness
- long-running agents
- software engineering
- Anthropic
cover: https://cdn.sanity.io/images/4zrzovbb/website/84a488382e0428a5eebade574af047e5d3b610ab-2400x1260.png
---

# 长时运行应用开发的 harness 设计

*作者 Prithvi Rajasekaran，Anthropic [Labs](https://www.anthropic.com/news/introducing-anthropic-labs) 团队成员。*

过去几个月里，我一直在处理两个相互关联的问题：让 Claude 产出高质量前端设计，以及让它在无需人工干预的情况下构建完整应用。这项工作源于我们此前在[前端设计 skill](https://github.com/anthropics/claude-code/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md)和[长时运行编码智能体 harness](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)上的探索；我和同事通过提示词工程与 harness 设计把 Claude 的表现提升到远高于基线的水平——但两者最终都碰到了天花板。

为了突破，我寻找能跨越两个相当不同领域的新型 AI 工程方法：一个由主观品味定义，另一个由可验证的正确性与可用性定义。受[生成对抗网络](https://en.wikipedia.org/wiki/Generative_adversarial_network)（GAN）启发，我设计了一个由**生成器**与**评估器**智能体构成的多智能体结构。要构建能可靠、且有品味地为输出打分的评估器，首先必须发展一组标准，将“这个设计好吗？”之类的主观判断变成具体、可评分的术语。

随后，我将这些技术应用于长时运行的自主编码，并沿用了此前 harness 工作中的两项经验：把构建拆分为可处理的块，以及使用结构化工件在会话间交接上下文。最终结果是一个由规划器、生成器和评估器组成的三智能体架构，能在持续数小时的自主编码会话中产出丰富的全栈应用。

## 为什么朴素的实现不够好

我们此前已经展示，harness 设计会显著影响长时运行智能体编码的有效性。在此前一项[实验](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)中，我们使用初始化智能体把产品规格拆分成任务列表，并使用编码智能体一次实现一个功能，然后交接工件以在会话间传递上下文。更广泛的开发者社区也得出了类似洞见，例如“[Ralph Wiggum](https://ghuntley.com/ralph/)”方法会用 hooks 或脚本让智能体保持连续迭代循环。

但有些问题依旧存在。对于更复杂的任务，智能体仍倾向于随着时间推移脱轨。分析这个问题时，我们观察到智能体执行此类任务时有两种常见失败模式。

第一种是，随着上下文窗口填满，模型往往会在长任务上失去连贯性（参见我们关于[上下文工程](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)的文章）。有些模型还表现出“上下文焦虑”：当它们接近自己认为的上下文上限时，开始过早收尾工作。上下文重置——完全清空上下文窗口并启动新的智能体，再配合携带前一智能体状态和下一步行动的结构化交接——可以同时解决这两个问题。

这不同于压缩：压缩是在原处概括对话的早期部分，让同一个智能体能在缩短的历史上继续工作。虽然压缩保持了连续性，却无法给智能体一张白纸，因此上下文焦虑仍会持续。重置提供一张白纸，代价是交接工件必须含有足够状态，才能让下一个智能体无缝接续工作。在此前测试中，我们发现 Claude Sonnet 4.5 的上下文焦虑足够明显，仅靠压缩不足以支持强大的长任务表现，因此上下文重置成为 harness 设计的必要部分。这解决了核心问题，但也给每次 harness 运行增加了编排复杂度、token 开销和延迟。

第二个我们此前尚未解决的问题是自我评估。当被要求评估自己产出的工作时，智能体往往会自信地称赞它——即使在人类观察者看来质量显然平平。对于设计这类主观任务，这个问题尤其突出，因为没有可验证软件测试那样的二元检查。布局是否精致或普通是判断问题，而智能体在给自己的作品评分时稳定地偏向正面。

不过，即使对于确有可验证结果的任务，智能体在完成任务时仍有时会展现出糟糕判断，从而妨碍自身表现。将执行工作的智能体与评判它的智能体分离，证明是解决此问题的有力杠杆。单靠分离不会立即消除宽容倾向；评估器仍是倾向于宽待 LLM 生成输出的 LLM。但将独立评估器调校得更怀疑，远比让生成器批判自己的作品更可行；一旦这种外部反馈存在，生成器便有了可据以迭代的具体对象。

## 前端设计：让主观质量可评分

我首先在前端设计上试验，这里自我评估问题最明显。没有任何干预时，Claude 通常会倾向于安全、可预测的布局，它们在技术上可用，却在视觉上平淡无奇。

两个洞见塑造了我为前端设计构建的 harness。第一，虽然美感无法被完全简化成一个分数，个人品味也总会不同，但可以通过编码设计原则和偏好的评分标准予以改善。“这个设计漂亮吗？”很难稳定回答，但“它是否遵循我们优秀设计的原则？”给了 Claude 可据以评分的具体对象。第二，通过把前端生成与前端评分分离，我们可以创建一条推动生成器走向更强输出的反馈循环。

考虑到这一点，我写了四项评分标准，并在提示词中同时交给生成器与评估器智能体：

- **设计质量：**设计是否像一个连贯整体，而非零散部件的集合？这里的强工作意味着颜色、排版、布局、图像和其他细节结合起来，创造独特的情绪和身份。
- **原创性：**是否有定制决策的证据，还是只是模板布局、库默认值和 AI 生成模式？人类设计师应能看出有意的创意选择。未经修改的库存组件——或紫色渐变覆盖白色卡片等 AI 生成的明显痕迹——在此不合格。
- **工艺：**技术执行：排版层级、间距一致性、颜色和谐度、对比度。它是能力检查而非创造力检查。大多数合理实现默认就能做好；失败意味着基础能力已损坏。
- **功能性：**独立于美感的可用性。用户能理解界面做什么、找到主要操作并无需猜测地完成任务吗？

我比工艺和功能性更强调设计质量与原创性。Claude 默认在工艺和功能性上已经得分不错，因为所需的技术能力往往自然地来自模型。但在设计与原创性上，Claude 经常产出至多只能说平淡的输出。这些标准明确惩罚高度通用的“AI 垃圾”模式；通过更重地加权设计和原创性，它推动模型承担更多美学风险。

我用带有详细分数拆解的少样本示例校准评估器。这确保评估器判断与我的偏好一致，并减少迭代间的分数漂移。

我在 [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview) 上构建了这个循环，因此编排相当直接。生成器智能体先根据用户提示词创建 HTML/CSS/JS 前端。我给评估器配备了 Playwright MCP，让它在为每项标准评分并写出详细批评前，能直接与线上页面互动。实践中，评估器会自行导航页面、截图并仔细研究实现，然后才产出评估。该反馈会作为下一次迭代输入流回生成器。我每次生成运行 5 到 15 次迭代，每一次通常会在生成器回应评估器批评时，将它推向更有辨识度的方向。由于评估器是主动导航页面而非对静态截图评分，每个循环都需要真实墙钟时间。完整运行最长可达四小时。我也指示生成器在每次评估后做战略决策：如果分数走势良好，就细化当前方向；若方法不奏效，则转向完全不同的美学方向。

在多次运行中，评估器的判断会随迭代改善，随后进入平台期，但仍有余量。一些生成是渐进地细化；另一些则在迭代之间发生强烈的美学转向。

评分标准的措辞以我未完全预料的方式引导了生成器。包含“最好的设计具有博物馆级品质”之类的短语，会把设计推向一种特定的视觉收敛，说明与标准相关的提示词直接塑造了输出特征。

尽管分数总体会随迭代提升，模式并不总是干净的线性。后期实现整体往往更好，但我经常看到自己偏爱中间迭代而非最后迭代的情形。实现复杂度也倾向于随轮次增加，因为生成器会回应评估器反馈，尝试更具雄心的解决方案。即便在第一次迭代，输出也明显优于完全没有提示的基线，这表明这些标准和相关语言本身已在任何评估器反馈带来进一步细化之前，将模型引离通用默认值。

有一个值得注意的例子：我提示模型为一家荷兰艺术博物馆创建网站。到第九次迭代，它已经为一家虚构博物馆产出简洁的深色主题着陆页。页面视觉上精致，但基本符合我的预期。随后在第十个循环，它完全丢弃这个方向，把网站重新想象成一种空间体验：一个用 CSS 透视渲染棋盘地板的 3D 房间，艺术品以自由形式位置挂在墙上，并以门洞式导航在画廊房间之间移动，而非滚动或点击。这是一种我此前从未在单次生成中看到过的创造性跃迁。

<video controls="" src="https://cdn.sanity.io/files/4zrzovbb/website/9877febd34432f7f582aecd0023b951223605c6a.mp4"></video>

## 扩展到全栈编码

基于这些发现，我把这一受 GAN 启发的模式应用于全栈开发。生成器—评估器循环自然映射到软件开发生命周期，其中代码审查和 QA 发挥着与设计评估器相同的结构性作用。

### 架构

在此前的[长时运行 harness](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)中，我们已通过初始化智能体、一次处理一个功能的编码智能体，以及会话间的上下文重置，解决了连贯的多会话编码问题。上下文重置是一项关键突破：harness 使用 Sonnet 4.5，它表现出前文提到的“上下文焦虑”倾向。构建一个可在上下文重置中良好运作的 harness，是让模型持续专注于任务的关键。Opus 4.5 很大程度上自行消除了这种行为，因此我能够完全从这个 harness 中去掉上下文重置。智能体在整个构建过程中作为一个连续会话运行，由 [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview) 的自动压缩处理一路增长的上下文。

在这项工作中，我基于原始 harness 的基础构建了一个三智能体系统，每个智能体解决我在先前运行中观察到的一个具体缺口。系统包含以下智能体角色：

**规划器：**我们此前的长时运行 harness 要求用户预先提供详细规格。我想自动化这一步，所以创建了一个规划器智能体，它接收一个简单的 1–4 句提示词，并将其扩展为完整产品规格。我提示它在范围上要雄心勃勃，并专注于产品语境和高层技术设计，而非详细技术实现。之所以如此强调，是因为如果规划器试图预先指定细粒度技术细节而且出错，规格中的错误会级联到下游实现中。更明智的做法似乎是限制智能体要产出的交付物，让它们在工作时自行找出路径。我还要求规划器寻找机会，把 AI 功能编入产品规格。（参见底部附录中的示例。）

**生成器：**此前 harness 中的一次一个功能方法很适合范围管理。我在此采用类似模型，指示生成器以 sprint 方式工作，每次从规格中接手一个功能。每个 sprint 用 React、Vite、FastAPI 和 SQLite（后来改为 PostgreSQL）技术栈实现应用，并要求生成器在每个 sprint 结束时自我评估工作，然后交接给 QA。它也使用 git 做版本控制。

**评估器：**此前 harness 产出的应用往往看起来令人印象深刻，但当你实际尝试使用时仍有真正的 bug。为捕捉它们，评估器会使用 Playwright MCP 像用户一样点击运行中的应用，测试 UI 功能、API 端点和数据库状态。随后它会根据发现的 bug，以及一组基于前端实验、适配为涵盖产品深度、功能性、视觉设计和代码质量的标准，对每个 sprint 评分。每项标准都有硬阈值，若有任一项低于阈值，sprint 就失败，生成器会得到关于问题所在的详细反馈。

每个 sprint 前，生成器和评估器会协商一份 sprint 合同：在写任何代码前，就该工作块的“完成”是什么样达成一致。这是因为产品规格有意保持高层，我想加入一步来弥合用户故事与可测试实现间的差距。生成器提出将构建什么、如何验证成功，评估器审查该提案以确保生成器在构建正确的东西。两者会迭代直至达成一致。

通信通过文件处理：一个智能体写入文件，另一个智能体读取并在该文件中回复，或写入一个由前者轮流读取的新文件。随后生成器根据已同意的合同构建，再把工作交给 QA。这既让工作忠实于规格，又避免过早地过度指定实现。

### 运行 harness

对于这个 harness 的第一个版本，我使用 Claude Opus 4.5，将用户提示词同时交给完整 harness 和单智能体系统以作比较。因为开始这些实验时 Opus 4.5 是我们最好的编码模型，所以选用了它。

我写下了以下提示词来生成一款复古电子游戏制作器：

> *创建一个 2D 复古游戏制作器，功能包括关卡编辑器、精灵编辑器、实体行为和可玩的测试模式。*

下表展示了 harness 类型、运行时长和总成本。

| **Harness** | **时长** | **成本** |
| --- | --- | --- |
| 单独运行 | 20 分钟 | $9 |
| 完整 harness | 6 小时 | $200 |

harness 的成本超过 20 倍，但输出质量的差异立刻显现。

我期望的是一个能构建关卡及其组件（精灵、实体、瓦片布局）、然后按下播放真正游玩关卡的界面。我先打开单独运行的输出，初始应用看上去符合这些期待。

然而，随着我不断点击，问题开始出现。布局浪费空间，固定高度面板让大部分视口空着。工作流很僵硬。尝试填充关卡时，它提示我先创建精灵和实体，但 UI 中没有任何内容指引我遵循这一顺序。更重要的是，实际游戏是坏的。我的实体出现在屏幕上，却没有任何东西响应输入。深入查看代码后发现，实体定义与游戏运行时之间的连接坏了，界面没有显示任何线索说明问题在哪里。

![](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2F23c98f1d7ae720bfb39190d50e0706c03b177ad8-1999x1320.png&w=3840&q=75)

打开单独 harness 创建的应用时的初始界面。

评估完单独运行后，我转而关注 harness 运行。该运行同样从一句提示词开始，但规划器步骤将其扩展成一份覆盖十个 sprint 的、包含 16 项功能的规格。它远超单独运行所尝试的范围。除核心编辑器和游玩模式外，规格还要求精灵动画系统、行为模板、音效与音乐、AI 辅助的精灵生成器与关卡设计器，以及带可分享链接的游戏导出。我给规划器访问了我们的[前端设计 skill](https://github.com/anthropics/claude-code/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md)，它阅读并用该 skill 为应用创建了视觉设计语言，作为规格的一部分。对于每个 sprint，生成器和评估器协商一份合同，定义该 sprint 的具体实现细节以及用于验证完成的可测试行为。

应用立刻展示出比单独运行更多的精致与流畅。画布使用整个视口，面板尺寸合理，界面具有与规格中设计方向一致的视觉身份。单独运行中看到的一些笨拙仍然存在——工作流依旧没有清楚表明，在尝试填充关卡前应先构建精灵和实体，我必须自己摸索。这更像基础模型产品直觉的缺口，而不是 harness 要解决的问题；不过它确实提示，harness 内的针对性迭代或可进一步提高输出质量。

在编辑器中操作时，新运行相对单独运行的优势更明显。精灵编辑器更丰富、功能更完整，有更清晰的工具调色板、更好的颜色选择器和更易用的缩放控件。

由于我要求规划器将 AI 功能编入规格，应用还内置了 Claude 集成，让我能通过提示词生成游戏的不同部分。这显著加快了工作流。

![](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2Fa8bef95425966495629095a5cb38bde4a8b13558-1999x997.png&w=3840&q=75)

初始界面：在完整 harness 构建的应用中创建新游戏。

最大的差异出现在游玩模式。我实际上能移动实体并游玩游戏。物理效果有一些粗糙边缘——我的角色跳到平台上但最终与平台重叠，直觉上不对——但核心功能是可用的，而单独运行未能做到。移动一会儿后，我确实遇到 AI 构建游戏关卡的一些局限。有一堵高墙，我无法跳过去，因此被卡住了。这说明 harness 还可以处理一些常识性改进和边缘情形，以进一步精炼应用。

查看日志时，很清楚评估器让实现保持与规格一致。每个 sprint 中，它都会走过 sprint 合同的测试标准，并通过 Playwright 操作运行中的应用，对任何偏离预期行为的内容提交 bug。合同非常细粒度——仅 Sprint 3 就有 27 条涵盖关卡编辑器的标准——而评估器的发现足够具体，无需额外调查即可行动。下表展示了评估器识别出的若干问题示例：

| **合同标准** | **评估器发现** |
| --- | --- |
| 矩形填充工具允许点击拖动，以所选瓦片填充矩形区域 | **失败** — 工具只会在拖动起点/终点放置瓦片，而非填满区域。`fillRectangle` 函数存在，但没有在 mouseUp 时被正确触发。 |
| 用户可以选择并删除已放置的实体生成点 | **失败** — `LevelEditor.tsx:892` 的 Delete 键处理器要求同时设置 `selection` 和 `selectedEntityId `，但点击实体只会设置 `selectedEntityId`。条件应为 `selection \|\| (selectedEntityId && activeLayer === 'entity')`。 |
| 用户可以通过 API 重新排序动画帧 | **失败** — `PUT /frames/reorder` 路由定义在 `/{frame_id}` 路由之后。FastAPI 会将 'r `eorder` ' 匹配为整数 frame\_id，并返回 422：“无法将字符串解析为整数。” |

要让评估器达到这个水平需要投入工作。开箱即用时，Claude 是一个糟糕的 QA 智能体。在早期运行中，我看着它识别出真实问题，接着又说服自己那些问题不重要，并仍然批准工作。它也倾向于浅层测试而非探测边缘情形，因此更细微的 bug 常常漏过。调校循环是阅读评估器日志，找出其判断与我不同的例子，并更新 QA 的提示词以解决那些问题。经过这轮开发循环的数次迭代后，评估器才以我认为合理的方式评分。即便如此，harness 输出仍显示了模型 QA 能力的限制：小的布局问题、局部显得不直观的交互，以及评估器没有充分操作、更深层嵌功能中未被发现的 bug。显然，通过进一步调校仍可获得更多验证余量。但与单独运行相比——后者应用的核心功能根本无法工作——提升是显而易见的。

### 迭代 harness

第一组 harness 结果令人鼓舞，但也很笨重、缓慢且昂贵。合乎逻辑的下一步是寻找在不降低表现的情况下简化 harness 的方法。这部分出于常识，也源于一个更一般的原则：harness 中的每个组件都编码了一个关于模型无法独自完成什么的假设；这些假设值得压力测试，既因为它们可能不正确，也因为随着模型进步它们很快就会过时。我们的博文[构建有效智能体](https://www.anthropic.com/research/building-effective-agents)将其核心思想表述为“找到尽可能简单的解决方案，只在需要时增加复杂性”；这也是所有维护智能体 harness 的人都会反复看到的模式。

在第一次简化尝试中，我大幅削减 harness 并尝试一些新颖想法，但无法复制原始版本的表现。它也变得很难分辨 harness 设计的哪些部分实际承重、以什么方式承重。基于那次经验，我转向更系统的方法：一次移除一个组件，并审查它对最终结果的影响。

在我经历这些迭代循环时，我们还发布了 Opus 4.6，这进一步激励我降低 harness 复杂度。有充分理由相信 4.6 比 4.5 需要更少的脚手架。正如我们的[发布博文：](https://www.anthropic.com/news/claude-opus-4-6)“\[Opus 4.6\] 规划更仔细，能更久地持续执行智能体任务，能在更大代码库中更可靠地操作，并具有更好的代码审查和调试技能来捕捉自己的错误。”它在长上下文检索上也有实质改善。这些都是 harness 被构建来补足的能力。

### 移除 sprint 结构

我先完全移除了 sprint 结构。sprint 结构曾帮助将工作拆成模型可以连贯处理的块。鉴于 Opus 4.6 的改进，有充分理由相信模型无需此类拆分就能原生处理这项工作。

我保留了规划器和评估器，因为两者都继续增添明显价值。没有规划器，生成器会缩小范围：面对原始提示词，它会在未先制定工作规格时就开始构建，最终创建功能比规划器所做更少的应用。

移除 sprint 结构后，我将评估器改为运行结束时的一次单独评审，而非每个 sprint 评分。由于模型强大得多，它改变了评估器对某些运行的承重程度；其有用性取决于任务位于模型能独自可靠完成范围的哪个位置。对于 4.5，这个边界很近：我们的构建处在生成器独自能做好的边缘，评估器会在整个构建中捕获有意义的问题。对于 4.6，模型原始能力提升，边界向外移动。过去需要评估器检查才能连贯实现的任务，现在通常落在生成器独自已能做好范围内；对于边界以内的任务，评估器变成不必要的开销。但对于仍位于生成器能力边缘的构建部分，评估器依旧带来真实提升。

实际含义是，评估器并非一个固定的“是或否”决定。当任务超出当前模型能独自可靠完成的范围时，它值得这份成本。

除结构简化外，我还添加提示词来改善 harness 如何将 AI 功能构建进每个应用，具体是让生成器构建一个能通过工具驱动应用自身功能的恰当智能体。这需要真正的迭代，因为相关知识足够新，Claude 的训练数据对它覆盖较少。但经过足够调校，生成器能正确构建智能体。

### 更新后 harness 的结果

为了测试更新后的 harness，我使用以下提示词生成一款数字音频工作站（DAW），即用于编曲、录制和混音歌曲的音乐制作程序：

> *使用 Web Audio API 在浏览器中构建一款功能完整的 DAW。*

这次运行仍然很长且昂贵，大约 4 小时，token 成本为 $124。

大部分时间花在构建器上，它在没有 Opus 4.5 所需的 sprint 拆分下，仍能连贯运行超过两小时。

| **智能体与阶段** | **时长** | **成本** |
| --- | --- | --- |
| 规划器 | 4.7 分钟 | $0.46 |
| 构建（第 1 轮） | 2 小时 7 分钟 | $71.08 |
| QA（第 1 轮） | 8.8 分钟 | $3.24 |
| 构建（第 2 轮） | 1 小时 2 分钟 | $36.89 |
| QA（第 2 轮） | 6.8 分钟 | $3.09 |
| 构建（第 3 轮） | 10.9 分钟 | $5.88 |
| QA（第 3 轮） | 9.6 分钟 | $4.06 |
| **V2 Harness 总计** | **3 小时 50 分钟** | **$124.70** |

与此前 harness 一样，规划器把一行提示词扩展为完整规格。从日志中，我可以看到生成器模型在规划应用和智能体设计、连接智能体，以及交给 QA 前测试它方面做得很好。

不过，QA 智能体仍捕捉到真实缺口。在其第一轮反馈中，它指出：

> 这是一个设计保真度出色、AI 智能体扎实、后端良好的强应用。主要失败点是功能完整性——尽管应用看起来令人印象深刻，AI 集成也运作良好，若干核心 DAW 功能却仅为展示，缺乏可交互深度：片段不能在时间线上拖动/移动；没有乐器 UI 面板（合成器旋钮、鼓垫）；也没有可视化效果编辑器（EQ 曲线、压缩器仪表）。这些不是边缘情形——它们是让 DAW 可用的核心交互，而规格中明确要求了它们。

在第二轮反馈中，它再次捕获若干功能缺口：

> 尚存缺口：
> \- 音频录制仍只是桩实现（按钮会切换，但未捕获麦克风）
> \- 未实现通过边缘拖动调整片段大小及切分片段
> \- 效果可视化是数字滑块，而非图形化（没有 EQ 曲线）

如果任其自行处理，生成器仍可能遗漏细节或将功能做成桩；QA 在捕捉这些由生成器修复的最后一公里问题方面仍有价值。

基于提示词，我期望得到一个能创建旋律、和声和鼓点，将它们编排成歌曲，并在途中获得集成智能体帮助的程序。下面的视频展示了结果。

<video controls="" src="https://cdn.sanity.io/files/4zrzovbb/website/555910f9adb3938734940224e7a6f4c7cbbbd8f2.mp4"></video>

该应用远非专业音乐制作程序，智能体的歌曲创作技能显然也还有很多提升空间。此外，Claude 实际上无法听见声音，这使 QA 反馈循环在音乐品味方面效果较弱。

但最终应用拥有功能性音乐制作程序的所有核心组件：可在浏览器中运行的编排视图、混音器和传输控制。除此之外，我能完全通过提示词拼出一小段歌曲：智能体设置速度和调性、写下一段旋律、构建鼓轨、调整混音器音量并添加混响。歌曲创作的核心原语都已具备，智能体也能自主地驱动它们，使用工具端到端地完成简单制作。你可以说它还不够音准完美——但它正在接近。

## 接下来是什么

随着模型持续进步，我们大致可以期待它们能够工作更久、处理更复杂任务。在某些情况下，这意味着围绕模型的 scaffold 会随时间变得不那么重要，开发者可以等待下一代模型，让某些问题自行消失。另一方面，模型越好，就越有空间开发能够完成超出模型基线能力的复杂任务的 harness。

考虑到这一点，这项工作有几项经验值得延续。针对正在构建的模型进行实验、阅读它在真实问题上的轨迹，并调校其表现以实现期望结果，始终是好做法。处理更复杂任务时，有时可以通过拆解任务并将专门智能体用于问题的各个方面来获得余量。新模型到来时，通常也应重新审视一个 harness：去掉不再对表现承重的部分，并加入新部分以实现此前不可能实现的更大能力。

从这项工作中，我的信念是：随着模型改进，有趣的 harness 组合空间并不会缩小。相反，它会移动；AI 工程师有趣的工作是不断发现下一个新颖组合。

## 致谢

特别感谢 Mike Krieger、Michael Agaby、Justin Young、Jeremy Hadfield、David Hershey、Julius Tarng、Xiaoyi Zhang、Barry Zhang、Orowa Sidker、Michael Tingley、Ibrahim Madha、Martina Long 和 Canyon Robbins 对这项工作的贡献。

也感谢 Jake Eaton、Alyssa Leonard 和 Stef Sequeira 对塑造本文提供的帮助。

## 附录

由规划器智能体生成的示例计划。

```
RetroForge - 2D Retro Game Maker

Overview
RetroForge is a web-based creative studio for designing and building 2D retro-style video games. It combines the nostalgic charm of classic 8-bit and 16-bit game aesthetics with modern, intuitive editing tools—enabling anyone from hobbyist creators to indie developers to bring their game ideas to life without writing traditional code.

The platform provides four integrated creative modules: a tile-based Level Editor for designing game worlds, a pixel-art Sprite Editor for crafting visual assets, a visual Entity Behavior system for defining game logic, and an instant Playable Test Mode for real-time gameplay testing. By weaving AI assistance throughout (powered by Claude), RetroForge accelerates the creative process—helping users generate sprites, design levels, and configure behaviors through natural language interaction.

RetroForge targets creators who love retro gaming aesthetics but want modern conveniences. Whether recreating the platformers, RPGs, or action games of their childhood, or inventing entirely new experiences within retro constraints, users can prototype rapidly, iterate visually, and share their creations with others.

Features
1. Project Dashboard & Management
The Project Dashboard is the home base for all creative work in RetroForge. Users need a clear, organized way to manage their game projects—creating new ones, returning to works-in-progress, and understanding what each project contains at a glance.

User Stories: As a user, I want to:

- Create a new game project with a name and description, so that I can begin designing my game
- See all my existing projects displayed as visual cards showing the project name, last modified date, and a thumbnail preview, so that I can quickly find and continue my work
- Open any project to enter the full game editor workspace, so that I can work on my game
- Delete projects I no longer need, with a confirmation dialog to prevent accidents, so that I can keep my workspace organized
- Duplicate an existing project as a starting point for a new game, so that I can reuse my previous work

Project Data Model: Each project contains:

Project metadata (name, description, created/modified timestamps)
Canvas settings (resolution: e.g., 256x224, 320x240, or 160x144)
Tile size configuration (8x8, 16x16, or 32x32 pixels)
Color palette selection
All associated sprites, tilesets, levels, and entity definitions

...
```
