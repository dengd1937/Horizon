---
title: 为 AI 智能体编写有效工具——借助 AI 智能体
source_url: https://www.anthropic.com/engineering/writing-tools-for-agents
source_domain: anthropic.com
published_date: '2025-09-11'
added_date: '2026-07-16'
slug: anthropic-com-20250911-effective-agent-tools
summary: Anthropic 介绍用原型、真实任务评估和智能体协作来改进工具的方法，并总结工具选择、命名空间、高信号响应、token 效率和工具描述提示词工程等原则。
tags:
- AI agents
- MCP
- tool design
- evaluations
- Anthropic
cover: https://cdn.sanity.io/images/4zrzovbb/website/91df4759f1037fb6073de772278cb71e6e4ee37d-2400x1260.png
---

# 为 AI 智能体编写有效工具——借助 AI 智能体 \ Anthropic

[Model Context Protocol（MCP）](https://modelcontextprotocol.io/docs/getting-started/intro) 可以让 LLM 智能体获得潜在数百种工具，以解决真实世界任务。但我们该如何让这些工具发挥最大效能？

本文介绍了我们在多种智能体 AI 系统中提升性能的最有效技术 <sup>1</sup>。

首先，我们将介绍如何：

- 构建并测试工具原型
- 与智能体一起创建并运行全面的工具评估
- 与 Claude Code 等智能体协作，自动提升工具性能

最后，我们将总结一路识别出的高质量工具编写原则：

- 选择应实现（以及不应实现）的正确工具
- 通过命名空间为功能划出清晰边界
- 从工具向智能体返回有意义的上下文
- 为 token 效率优化工具响应
- 对工具描述和规范进行提示词工程

![该图展示工程师如何使用 Claude Code 评估智能体工具的效能。](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2Fcdc027ad2730e4732168bb198fc9363678544f99-1920x1080.png&w=3840&q=75)

构建评估可以让你系统地衡量工具表现；你可以使用 Claude Code 针对该评估自动优化工具。

## 什么是工具？

在计算中，确定性系统在输入相同的情况下每次都会产生相同输出；而*非确定性*系统——如智能体——即使起始条件相同，也可能生成不同响应。

传统软件开发是在确定性系统之间建立契约。例如，像 `getWeather(“NYC”)` 这样的函数调用，每次都会以完全相同的方式获取纽约市天气。

工具是一类新软件，体现了确定性系统与非确定性智能体之间的契约。用户问“今天要带伞吗？”时，智能体可能调用天气工具、根据常识回答，或先询问所在地。偶尔，智能体还可能产生幻觉，甚至不理解该如何使用工具。

这意味着为智能体编写软件时必须从根本上改变方法：不能再像为其他开发者或系统编写函数和 API 那样编写工具与 [MCP 服务器](https://modelcontextprotocol.io/)，而要为智能体而设计。

我们的目标是扩大智能体能够有效解决大量任务的范围，让它们借助工具采用各种成功策略。幸运的是，根据我们的经验，对智能体最“符合人体工学”的工具，往往也出人意料地易于人类理解。

## 如何编写工具

本节说明如何与智能体协作，既编写工具，也改进你交给它们的工具。先快速搭建工具原型并在本地测试；接着运行全面评估以衡量之后的改动；随后与智能体并肩反复评估和改进，直到智能体在真实任务上表现强劲。

### 构建原型

如果不亲自上手，很难预判哪些工具让智能体觉得顺手、哪些不会。先快速搭建工具原型。如果你使用 [Claude Code](https://www.anthropic.com/claude-code) 编写工具（可能一次完成），为 Claude 提供工具依赖的软件库、API 或 SDK 文档会有帮助，其中也包括可能使用的 [MCP SDK](https://modelcontextprotocol.io/docs/sdk)。在官方文档站点中，常可找到对 LLM 友好的扁平 `llms.txt` 文档（例如我们的 [API 文档](https://docs.anthropic.com/llms.txt)）。

将工具封装为[本地 MCP 服务器](https://modelcontextprotocol.io/docs/develop/connect-local-servers)或 [Desktop extension](https://www.anthropic.com/engineering/desktop-extensions)（DXT），即可在 Claude Code 或 Claude Desktop 应用中连接并测试工具。

要把本地 MCP 服务器连接到 Claude Code，请运行 `claude mcp add <name> <command> [args...]`。

要把本地 MCP 服务器或 DXT 连接到 Claude Desktop 应用，请分别前往 `Settings > Developer` 或 `Settings > Extensions`。

工具也可以直接传入 [Anthropic API](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview) 调用，以进行程序化测试。

亲自测试工具以发现不顺畅之处；收集用户反馈，建立对预期工具支持的用例和提示词的直觉。

### 运行评估

接下来，需要通过运行评估来衡量 Claude 使用工具的效果。先生成大量以真实世界使用为基础的评估任务。我们建议与智能体协作分析结果，并决定如何改进工具。可在我们的[工具评估 cookbook](https://platform.claude.com/cookbook/tool-evaluation-tool-evaluation) 中查看这一端到端流程。

![该图衡量人工编写与 Claude 优化的 Slack MCP 服务器的测试集准确率。](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2F6e810aee67f3f3c955832fb7bf9033ffb0102000-1920x1080.png&w=3840&q=75)

我们内部 Slack 工具在留出测试集上的表现

**生成评估任务**

有了早期原型后，Claude Code 可以快速探索工具，并创建数十组提示词和响应对。提示词应来自真实世界用法，并基于真实的数据源与服务（例如内部知识库和微服务）。建议避免过于简单或流于表面的“沙盒”环境，它们无法以足够复杂度压力测试工具。强评估任务可能需要多次工具调用——潜在地达到数十次。

以下是强任务的例子：

- 下周与 Jane 安排一次会议，讨论最新的 Acme Corp 项目；附上上次项目规划会议的笔记，并预订会议室。
- 客户 ID 9182 报告一次购买尝试被扣款三次。找出所有相关日志条目，并确定是否还有其他客户受到同一问题影响。
- 客户 Sarah Chen 刚提交取消申请。准备一份挽留方案，并确定：(1) 她离开的原因；(2) 最有说服力的挽留优惠；以及 (3) 在提出优惠前需要注意的风险因素。

以下则是较弱的任务：

- 下周与 jane@acme.corp 安排会议。
- 在支付日志中搜索 `purchase_complete` 和 `customer_id=9182`。
- 按客户 ID 45892 查找取消申请。

每个评估提示词都应与可验证的响应或结果配对。验证器可以简单到比较真值与采样响应之间的精确字符串，也可以复杂到请 Claude 判断响应。避免过于严格的验证器，因为格式、标点或有效的替代表述等偶然差异可能让它们错误拒绝正确答案。

对每一对提示词与响应，还可以可选地指定你预计智能体在解决任务时会调用的工具，用于衡量智能体是否真正理解每个工具的用途。不过，由于正确解决任务可能有多条有效路径，应尽量避免过度规定或对策略过拟合。

**运行评估**

我们建议使用直接 LLM API 调用，以程序化方式运行评估。采用简单的智能体循环（用 `while` 循环包裹交替的 LLM API 与工具调用）：每个评估任务一个循环。每个评估智能体应收到一个任务提示词和你的工具。

在评估智能体的系统提示词中，我们建议要求智能体不仅输出用于验证的结构化响应块，还要输出推理和反馈块。让其在工具调用和响应块*之前*输出这些内容，可能会通过触发链式思维（CoT）行为来提高 LLM 的有效智能。

如果用 Claude 运行评估，可开启[交错思考](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking#interleaved-thinking)，以获得类似“开箱即用”的能力。这有助于探查智能体为什么调用或不调用某些工具，并突出工具描述和规范中可改进的具体领域。

除顶层准确率外，我们还建议收集其他指标，例如各次工具调用和任务的总运行时间、工具调用总数、token 总消耗及工具错误。跟踪工具调用可揭示智能体常见的工作流，并为合并工具提供机会。

![该图衡量人工编写与 Claude 优化的 Asana MCP 服务器的测试集准确率。](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2F3f1f47e80974750cd924bc51e42b6df1ad997fab-1920x1080.png&w=3840&q=75)

我们内部 Asana 工具在留出测试集上的表现

**分析结果**
智能体是发现问题、并就从互相矛盾的工具描述到低效工具实现与令人困惑的工具 schema 等一切提供反馈的有益伙伴。不过要记住，智能体在反馈和响应中省略的内容，往往比它们写出的内容更重要。LLM 并不总会[言由心生](https://www.anthropic.com/research/tracing-thoughts-language-model)。

观察智能体在哪里受阻或困惑。阅读评估智能体的推理和反馈（或 CoT）以找到粗糙边缘；审查原始转录（包括工具调用和工具响应），捕捉智能体 CoT 没有明确描述的行为。要读懂字里行间：评估智能体不一定知道正确答案和策略。

分析工具调用指标。大量冗余工具调用，可能意味着应适当调整分页或 token 上限参数；大量因无效参数导致的工具错误，则可能表示工具需要更清晰描述或更好示例。我们推出 Claude 的[网页搜索工具](https://www.anthropic.com/news/web-search)时，发现 Claude 会无谓地在工具的 `query` 参数上追加 `2025`，从而让搜索结果带偏、性能下降（我们通过改进工具描述将 Claude 引向正确方向）。

### 与智能体协作

你甚至可以让智能体替你分析结果并改进工具。只需把评估智能体的转录拼接起来，粘贴到 Claude Code。Claude 很擅长分析转录并一次性重构大量工具，例如确保在新增改动后工具实现与描述仍彼此一致。

事实上，本文大多数建议都来自我们反复用 Claude Code 优化内部工具实现的过程。评估建立在内部工作区之上，复现了内部工作流的复杂性，其中包括真实项目、文档和消息。

我们依赖留出测试集确保没有对“训练”评估过拟合。这些测试集显示，即使超过我们通过“专家”工具实现取得的提升——无论工具是研究人员手写还是 Claude 自己生成——仍可提取额外性能改进。

下一节将分享该过程中的一些收获。

## 编写有效工具的原则

本节将我们的经验提炼为几项编写有效工具的指导原则。

### 为智能体选择正确工具

工具更多并不总会带来更好结果。我们常见的错误，是工具仅仅包装了既有软件功能或 API 端点——而不管它们是否适合智能体。这是因为智能体相对于传统软件有不同的“可供性”，即它们感知使用这些工具所能采取行动的方式不同。

LLM 智能体的“上下文”有限（也就是它们一次可处理的信息量有限），而计算机内存便宜且充足。以在地址簿中查找联系人为例：传统软件能高效地一次存储和处理一个联系人，并逐一检查。

但是，如果 LLM 智能体使用一个返回*所有*联系人的工具，然后必须逐 token 阅读每一位联系人，它就在把有限上下文浪费在不相关信息上（想象通过从头到尾读每一页的暴力搜索来查地址簿）。更好、更自然的方法（对智能体和人类都一样）是先跳到相关页面（例如按字母查找）。

我们建议先构建少量面向特定高影响工作流、与评估任务匹配的深思熟虑的工具，再在此基础上扩展。在地址簿案例中，你可以实现 `search_contacts` 或 `message_contact`，而不是 `list_contacts`。

工具可以合并功能，在内部处理潜在的*多个*离散操作（或 API 调用）。例如，工具可以为响应补充相关元数据，或在一次调用中处理经常串联的多步骤任务。

以下是一些例子：

- 与其实现 `list_users`、`list_events` 和 `create_event`，不如考虑实现会查找可用时间并安排会议的 `schedule_event`。
- 与其实现 `read_logs`，不如考虑实现只返回相关日志行及少量周边上下文的 `search_logs`。
- 与其实现 `get_customer_by_id`、`list_transactions` 和 `list_notes`，不如实现一次汇编客户最近且相关信息的 `get_customer_context`。

确保构建的每个工具都有清晰、独特的目的。工具应让智能体像拥有相同底层资源的人类那样细分并解决任务，同时减少原本会被中间输出消耗的上下文。

工具过多或相互重叠，也会分散智能体追求高效策略的注意力。谨慎、有选择地规划要构建（或不构建）的工具，确实会有回报。

### 为工具划分命名空间

AI 智能体可能会获得数十个 MCP 服务器和数百个不同工具的访问权，其中包括其他开发者提供的工具。工具功能重叠或目的模糊时，智能体会不知道该用哪一个。

命名空间（以共同前缀归组相关工具）有助于为大量工具划出边界；MCP 客户端有时默认会这样做。例如，按服务命名空间化工具（如 `asana_search`、`jira_search`），以及按资源命名空间化工具（如 `asana_projects_search`、`asana_users_search`），都能帮助智能体在正确时机选择正确工具。

我们发现，在前缀式与后缀式命名空间之间选择，会对工具使用评估造成不可忽视的影响。效果因 LLM 而异，因此鼓励你依据自身评估选择命名方案。

智能体可能调用错误工具、用错误参数调用正确工具、调用的工具过少，或错误处理工具响应。通过有选择地实现名称能反映任务自然划分的工具，你同时减少了载入智能体上下文的工具与工具描述数量，并把部分智能体计算从智能体上下文转移回工具调用本身，从而降低智能体总体出错风险。

### 从工具返回有意义的上下文

同样地，工具实现应注意只向智能体返回高信号信息。它们应优先考虑上下文相关性而非灵活性，并避开低层技术标识符（如 `uuid`、`256px_image_url`、`mime_type`）。`name`、`image_url` 和 `file_type` 等字段更可能直接影响智能体后续行动和响应。

智能体通常也比起晦涩标识符，更能成功处理自然语言名称、术语或标识。我们发现，仅把任意字母数字 UUID 解析为更具语义、更可理解的语言（甚至是从 0 开始的 ID 方案），就能通过减少幻觉显著提升 Claude 在检索任务中的精度。

在一些情形中，智能体可能需要同时与自然语言和技术标识符输出交互，以便触发下游工具调用（例如 `search_user(name=’jane’)` → `send_message(id=12345)`）。可以通过暴露一个简单的 `response_format` 枚举参数来同时支持两者，让智能体控制工具返回 `“concise”` 还是 `“detailed”` 响应（如下图）。

你还可以增加更多格式以获得更大灵活性，类似 GraphQL 可选择接收哪些信息。以下是控制工具响应详细程度的 ResponseFormat 枚举示例：

```
enum ResponseFormat {
   DETAILED = "detailed",
   CONCISE = "concise"
}
```

下面是详细工具响应的例子（206 token）：

![该代码片段展示详细工具响应示例。](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2F5ed0d30526bf68624f335d075b8c1541be3bb595-1920x1006.png&w=3840&q=75)

该代码片段展示详细工具响应示例。

下面是简洁工具响应的例子（72 token）：

![该代码片段展示简洁工具响应示例。](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2Fd4f649a66482efb5a80cf14ea85e84974ede1c49-1920x725.png&w=3840&q=75)

Slack 讨论串及其回复由唯一的 thread_ts 标识；获取讨论串回复需要该标识，其他 ID（channel_id、user_id）可从“detailed”工具响应中取得，以支持需要这些信息的后续调用。“concise”工具响应只返回讨论串内容，不含 ID。在该例中，工具响应仅使用约三分之一的 token。

即便是工具响应结构——例如 XML、JSON 或 Markdown——也会影响评估性能；不存在一体适用的解决方案。因为 LLM 基于下一个 token 预测进行训练，往往在与其训练数据匹配的格式上表现更好。最佳响应结构会因任务和智能体而大不相同；我们鼓励你根据自己的评估选择。

### 为 token 效率优化工具响应

优化上下文质量很重要，但优化工具响应返回给智能体的上下文*数量*也同样重要。

对于任何可能消耗大量上下文的工具响应，我们建议以合理的默认参数实现分页、范围选择、过滤和/或截断的组合。对 Claude Code，我们默认将工具响应限制在 25,000 token。我们预计智能体的有效上下文长度会随着时间增长，但上下文高效工具的需求仍将存在。

若选择截断响应，务必用有帮助的指令引导智能体。可直接鼓励智能体采用 token 更高效的策略，例如针对知识检索任务进行许多小而有针对性的搜索，而不是一次宽泛搜索。同样，如果工具调用产生错误（如输入验证期间），可以对错误响应做提示词工程，使其清楚传达具体、可行动的改进，而非给出晦涩错误码或回溯。

下面是被截断工具响应的例子：

![该图展示被截断工具响应示例。](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2Fe440d6a69d0ca80e71f3bec5c2d00906ff03ce6d-1920x1162.png&w=3840&q=75)

该图展示被截断工具响应示例。

下面是不具帮助性的错误响应示例：

![该图展示不具帮助性的工具响应示例。](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2F2445187904704fec8c50af0b950e310ba743fac2-1920x733.png&w=3840&q=75)

该图展示不具帮助性的工具响应示例。

下面是有帮助的错误响应示例：

![该图展示有帮助的错误响应示例。](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2F810661bd44a35fb273806ae95160040155978c3e-1920x850.png&w=3840&q=75)

工具截断和错误响应可以引导智能体采取 token 更高效的工具使用行为（使用过滤或分页），或给出格式正确的工具输入示例。

### 对工具描述进行提示词工程

现在来到提升工具效果的最有效方法之一：对工具描述和规范进行提示词工程。由于这些内容会载入智能体上下文，它们能够共同把智能体引向有效的工具调用行为。

编写工具描述和规范时，设想如何向团队的新员工说明工具。考虑你可能默认带入的上下文——专门查询格式、小众术语定义、底层资源之间的关系——并把它明确写出。通过清楚描述（并用严格数据模型强制）预期输入和输出，避免歧义。尤其是输入参数必须命名明确：与其将参数命名为 `user`，不如命名为 `user_id`。

借助评估，你能更有把握地衡量提示词工程的影响。即使对工具描述做很小的改进，也可能带来显著提升。Claude Sonnet 3.5 在我们精确改进工具描述之后，于 [SWE-bench Verified](https://www.anthropic.com/engineering/swe-bench-sonnet) 评估中取得了最先进性能，错误率大幅下降，任务完成度提高。

在[开发者指南](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use#best-practices-for-tool-definitions)中可找到其他工具定义最佳实践。若为 Claude 构建工具，我们还建议了解工具如何动态载入 Claude 的[系统提示词](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use#tool-use-system-prompt)。最后，若为 MCP 服务器编写工具，[工具注解](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)可以披露哪些工具需要开放世界访问或会执行破坏性改动。

## 展望

要为智能体构建有效工具，我们需要把软件开发实践从可预测、确定性的模式，转向非确定性模式。

通过本文所述的迭代、评估驱动流程，我们识别出工具成功的一致模式：有效工具被有意而清晰地定义，审慎使用智能体上下文，可在多样工作流中组合，并使智能体能直觉地解决真实任务。

未来，智能体与世界交互的具体机制会继续演化——从 MCP 协议更新到基础 LLM 的升级。通过系统、评估驱动的方法改进工具，我们能够确保随着智能体能力增强，它们使用的工具也同步演进。

## 致谢

本文由 Ken Aizawa 撰写；Research 团队（Barry Zhang、Zachary Witten、Daniel Jiang、Sami Al-Sheikh、Matt Bell、Maggie Vo）、MCP 团队（Theodora Chu、John Welsh、David Soria Parra、Adam Jones）、Product Engineering（Santiago Seira）、Marketing（Molly Vorwerck）、Design（Drew Roper）与 Applied AI（Christian Ryan、Alexander Bricken）的同事提供了宝贵贡献。

<sup>1</sup> 不包括训练底层 LLM 本身。

[![带有复杂几何形状与精细表面纹理的互锁拼图块](https://www-cdn.anthropic.com/images/4zrzovbb/website/43abe7e54b56a891e74a8542944dfbd33f07f49c-1000x1000.svg)](https://anthropic.skilljar.com/)
