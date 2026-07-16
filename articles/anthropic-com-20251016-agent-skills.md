---
title: 用 Agent Skills 赋予智能体现实世界的能力
source_url: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
source_domain: anthropic.com
published_date: '2025-10-16'
added_date: '2026-07-16'
slug: anthropic-com-20251016-agent-skills
summary: Anthropic 介绍 Agent Skills：通过可组合的指令、脚本和资源，将通用智能体转化为具备领域流程知识的专门智能体。
tags:
- AI agents
- Agent Skills
- Anthropic
cover: https://cdn.sanity.io/images/4zrzovbb/website/f10f90c11a484ad8bdf11ffcd9f6e08cfd9358b8-2400x1260.png
---

# 用 Agent Skills 赋予智能体现实世界的能力 \ Anthropic

*更新：我们已将 [*Agent Skills*](https://agentskills.io/) 发布为支持跨平台可移植性的开放标准。（2025 年 12 月 18 日）*

随着模型能力不断提升，我们如今可以构建能够与完整计算环境交互的通用智能体。例如，[Claude Code](https://claude.com/product/claude-code) 可以利用本地代码执行和文件系统，完成跨领域的复杂任务。但随着这些智能体愈发强大，我们需要更具可组合性、可扩展性和可移植性的方式，为它们配备领域专长。

这促使我们创建了 [**Agent Skills**](https://www.anthropic.com/news/skills)：由指令、脚本和资源组成的有组织文件夹，智能体可以发现并按需加载它们，以便在特定任务上发挥更好表现。Skills 将你的专业知识打包为 Claude 可组合使用的资源，扩展 Claude 的能力，并将通用智能体转化为适合你需求的专门智能体。

为智能体构建 skill，就像为新员工准备入职指南。与其为每个用例构建零散、专门设计的智能体，任何人现在都可以通过捕捉和共享自己的流程性知识，以可组合的能力来专门化智能体。本文将说明 Skills 是什么、它们如何工作，并分享构建自身 Skills 的最佳实践。

![要启用 skills，只需为智能体编写一个包含自定义指引的 SKILL.md 文件。](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2Fddd7e6e572ad0b6a943cacefe957248455f6d522-1650x929.jpg&w=3840&q=75)

一个 skill 是包含 `SKILL.md` 文件的目录，其中组织了可为智能体增添额外能力的指令、脚本和资源文件夹。

## Skill 的组成

为了解 Skills 如何实际运作，我们来看一个真实案例：它是支持 [Claude 最近推出的文档编辑能力](https://www.anthropic.com/news/create-files) 的 skills 之一。Claude 已经很擅长理解 PDF，但直接操作它们的能力仍有限（例如填写表单）。这个 [PDF skill](https://github.com/anthropics/skills/tree/main/document-skills/pdf) 则让我们能够为 Claude 赋予这些新能力。

最简单的 skill 是一个包含 `SKILL.md` 文件的目录。该文件必须以 YAML frontmatter 开始，其中含有两项必需元数据：`name` 和 `description`。启动时，智能体会将每个已安装 skill 的 `name` 和 `description` 预加载到系统提示词中。

这些元数据是**渐进式披露**的**第一层**：它们提供刚好足够的信息，使 Claude 知道每个 skill 应在何时使用，而不必将其全部加载到上下文中。该文件的实际正文则是第二层细节。如果 Claude 认为该 skill 与当前任务有关，就会通过将完整 `SKILL.md` 读入上下文来加载它。

![SKILL.md 文件的组成，包括相关元数据：name、description，以及与该 skill 应执行的具体操作相关的上下文。](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2F6f22d8913dbc6228e7f11a41e0b3c124d817b6d2-1650x929.jpg&w=3840&q=75)

SKILL.md 文件必须以 YAML Frontmatter 开头，包含文件名和描述；这些内容会在启动时载入系统提示词。

随着 skill 复杂度增加，它们可能包含无法装入单一 `SKILL.md` 的过多上下文，或只在特定场景相关的上下文。这时，skill 可以在 skill 目录内打包额外文件，并从 `SKILL.md` 按名称引用它们。这些额外的链接文件构成第三层（及更深层）细节，Claude 只会在需要时选择性地导航和发现它们。

在下方的 PDF skill 中，`SKILL.md` 引用了两个额外文件（`reference.md` 和 `forms.md`），skill 作者选择将它们与核心 `SKILL.md` 一同打包。通过将填写表单的指令移至单独的 `forms.md` 文件，skill 作者能够保持核心内容精简，并相信 Claude 只会在填写表单时才读取 `forms.md`。

![如何将额外内容打包进 SKILL.md 文件。](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2F191bf5dd4b6f8cfe6f1ebafe6243dd1641ed231c-1650x1069.jpg&w=3840&q=75)

你可以将更多上下文（通过额外文件）纳入 skill；随后 Claude 可根据系统提示词触发它们。

渐进式披露是使 Agent Skills 具有灵活性和可扩展性的核心设计原则。就像一本组织良好的手册：先给出目录，再给出特定章节，最后提供详细附录；Skills 让 Claude 只在需要时加载信息：

![该图展示了 Skills 中上下文的渐进式披露。](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2Fa3bca2763d7892982a59c28aa4df7993aaae55ae-2292x673.jpg&w=3840&q=75)

该图展示了 Skills 中上下文的渐进式披露。

具备文件系统和代码执行工具的智能体，在处理某项任务时不必把一个 skill 的全部内容读入上下文窗口。这意味着可打包进 skill 的上下文量实际上没有上限。

### Skills 与上下文窗口

下图展示了当用户消息触发某个 skill 时，上下文窗口如何变化。

![该图展示 skills 如何在你的上下文窗口中被触发。](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2F441b9f6cc0d2337913c1f41b05357f16f51f702e-1650x929.jpg&w=3840&q=75)

Skills 通过系统提示词在上下文窗口中被触发。

图中展示的操作序列如下：

1. 开始时，上下文窗口包含核心系统提示词、每个已安装 skill 的元数据，以及用户的初始消息；
2. Claude 通过调用 Bash 工具读取 `pdf/SKILL.md` 的内容，从而触发 PDF skill；
3. Claude 选择读取 skill 所打包的 `forms.md` 文件；
4. 最后，Claude 在加载相关指令后继续处理用户任务。

### Skills 与代码执行

Skills 还可以包含 Claude 可自行决定执行的代码，作为工具使用。

大型语言模型很擅长许多任务，但某些操作更适合传统代码执行。例如，通过生成 token 来排序一个列表，远比直接运行排序算法昂贵。除效率考量之外，许多应用还需要只有代码才能提供的确定性可靠性。

在我们的例子中，PDF skill 包含一个预先编写的 Python 脚本，用于读取 PDF 并提取所有表单字段。Claude 可以运行该脚本，而不需要把脚本或 PDF 读入上下文。由于代码具有确定性，此工作流也保持一致且可复现。

![该图展示代码如何通过 Skills 被执行。](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2Fc24b4a2ff77277c430f2c9ef1541101766ae5714-1650x929.jpg&w=3840&q=75)

Skills 可以根据任务性质，包含供 Claude 自行决定执行的代码。

## 开发和评估 Skills

以下是开始编写和测试 skills 的一些实用建议：

- **从评估开始：** 让智能体执行有代表性的任务，观察它们在哪些地方受阻或需要额外上下文，以识别能力缺口；然后逐步构建 skills 来弥补这些缺口。
- **为规模而组织：** 当 `SKILL.md` 变得难以驾驭时，将其拆分为独立文件并建立引用。如果某些上下文彼此互斥，或很少需要同时使用，分离这些路径将减少 token 用量。代码还可以同时充当可执行工具和文档；应清楚说明 Claude 应直接运行脚本，还是将其读入上下文作为参考。
- **从 Claude 的视角思考：** 在真实场景中监控 Claude 如何使用 skill，并根据观察结果迭代：留意意外的轨迹或对特定上下文的过度依赖。尤其要关注 skill 的 `name` 和 `description`，Claude 会在决定是否针对当前任务触发 skill 时使用它们。
- **与 Claude 一起迭代：** 当你与 Claude 处理任务时，让 Claude 将成功的方法和常见错误沉淀为 skill 中可复用的上下文与代码。如果它在用 skill 完成任务时偏离轨道，请让它反思出了什么问题。这个过程将帮助你发现 Claude 实际需要哪些上下文，而不是试图预先预测一切。

### 使用 Skills 的安全注意事项

Skills 通过指令和代码为 Claude 带来新能力。这使它们很强大，但也意味着恶意 skill 可能会在环境中引入漏洞，或指使 Claude 外泄数据、执行非预期操作。

我们建议只安装来自可信来源的 skills。安装可信度较低的 skill 时，应在使用前彻底审计：先阅读 skill 所打包文件的内容以理解其作用，尤其留意代码依赖项，以及图像、脚本等打包资源。同样，也要留意 skill 中要求 Claude 连接到潜在不可信外部网络源的指令或代码。

## Skills 的未来

Agent Skills [现已得到支持](https://www.anthropic.com/news/skills)，可用于 [Claude.ai](http://claude.ai/redirect/website.v1.6378569c-6077-4c19-8395-18af0a6f84fc)、Claude Code、Claude Agent SDK 和 Claude Developer Platform。

未来数周，我们将继续添加支持创建、编辑、发现、共享和使用 Skills 全生命周期的功能。我们尤其期待 Skills 帮助组织和个人分享其上下文与工作流；还会探索 Skills 如何通过教会智能体更复杂的、涉及外部工具和软件的工作流，来补充 [Model Context Protocol](https://modelcontextprotocol.io/)（MCP）服务器。

展望更远的未来，我们希望让智能体能够自行创建、编辑和评估 Skills，从而将自身的行为模式编码为可复用能力。

Skills 是一个简单的概念，并拥有相应简洁的格式。正是这种简洁性，让组织、开发者和终端用户更容易构建定制化智能体，并赋予它们新能力。

我们很期待看到大家的作品。可通过查看我们的 Skills [文档](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) 和 [cookbook](https://github.com/anthropics/claude-cookbooks/tree/main/skills) 开始。

## 致谢

本文由 Barry Zhang、Keith Lazuka 与 Mahesh Murag 撰写；他们都很喜欢文件夹。特别感谢 Anthropic 内部许多倡导、支持并构建 Skills 的同事。
