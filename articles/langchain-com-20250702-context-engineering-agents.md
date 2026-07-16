---
title: 上下文工程
source_url: https://www.langchain.com/blog/context-engineering-for-agents
source_domain: langchain.com
published_date: '2025-07-02'
added_date: '2026-07-16'
slug: langchain-com-20250702-context-engineering-agents
summary: LangChain 总结面向智能体的上下文工程四种策略：写入、选择、压缩与隔离上下文，并说明如何用 LangGraph 与 LangSmith 实现、评估和迭代这些策略。
tags:
- AI agents
- context engineering
- LangGraph
- LangChain
cover: https://cdn.prod.website-files.com/65c81e88c254bb0f97633a71/69cbaaa5d3aab32815f8592a_Context-Engineering.png
---

# 上下文工程

![](https://cdn.prod.website-files.com/65c81e88c254bb0f97633a71/69cbaaa5d3aab32815f8592a_Context-Engineering.png)

## 要点速览

智能体需要上下文来完成任务。上下文工程是在智能体轨迹的每一步，恰到好处地用信息填充上下文窗口的艺术与科学。本文通过评述各种流行智能体和论文，拆解上下文工程的几种常见策略——**写入、选择、压缩与隔离**。随后说明 LangGraph 如何被设计来支持它们！

**还可在[**此处**](https://youtu.be/4GiqzUHD5AA?ref=blog.langchain.com)**观看我们关于上下文工程的视频。**

![](https://cdn.prod.website-files.com/65c81e88c254bb0f97633a71/69cbaaa8d3aab32815f859f4_image-4.png)

上下文工程的通用类别

## 上下文工程

正如 Andrej Karpathy 所说，LLM 就像[一种新型操作系统](https://www.youtube.com/watch?si=-aKY-x57ILAmWTdw&t=620&v=LCEmiRjPEtQ&feature=youtu.be&ref=blog.langchain.com)。LLM 如同 CPU，其[上下文窗口](https://docs.anthropic.com/en/docs/build-with-claude/context-windows?ref=blog.langchain.com)如同 RAM，充当模型的工作记忆。与 RAM 一样，LLM 的上下文窗口[容量](https://lilianweng.github.io/posts/2023-06-23-agent/?ref=blog.langchain.com)也有限，难以承载各种上下文来源。正如操作系统会策展哪些内容能进入 CPU 的 RAM，我们可以认为“上下文工程”扮演着类似角色。[Karpathy 精炼地概括了这一点](https://x.com/karpathy/status/1937902205765607626?ref=blog.langchain.com)：

> *\[上下文工程是\]“……为下一步以恰到好处的信息填充上下文窗口的精细艺术与科学。”*

![](https://cdn.prod.website-files.com/65c81e88c254bb0f97633a71/69cbaaa8d3aab32815f859e3_image-1.png)

LLM 应用中常用的上下文类型

构建 LLM 应用时，我们需要管理哪些类型的上下文？上下文工程是一个适用于几种不同上下文类型的[总括概念](https://x.com/dexhorthy/status/1933283008863482067?ref=blog.langchain.com)：

- **指令**——提示词、记忆、few-shot 示例、工具描述等
- **知识**——事实、记忆等
- **工具**——工具调用的反馈

## 面向智能体的上下文工程

今年，对[智能体](https://www.anthropic.com/engineering/building-effective-agents?ref=blog.langchain.com)的兴趣大幅增长，因为 LLM 在[推理](https://platform.openai.com/docs/guides/reasoning?api-mode=responses&ref=blog.langchain.com)和[工具调用](https://www.anthropic.com/engineering/building-effective-agents?ref=blog.langchain.com)方面变得更强。[智能体](https://www.anthropic.com/engineering/building-effective-agents?ref=blog.langchain.com)会交错进行 [LLM 调用与工具调用](https://www.anthropic.com/engineering/building-effective-agents?ref=blog.langchain.com)，常常用于[长时运行任务](https://blog.langchain.com/introducing-ambient-agents/)。智能体交错进行 [LLM 调用与工具调用](https://www.anthropic.com/engineering/building-effective-agents?ref=blog.langchain.com)，借助工具反馈决定下一步。

![](https://cdn.prod.website-files.com/65c81e88c254bb0f97633a71/69cbaaa8d3aab32815f859dd_image-2.png)

智能体交错进行 LLM 调用和工具调用，并使用工具反馈决定下一步

然而，长时运行任务和不断累积的工具调用反馈，意味着智能体常会使用大量 token。这会造成许多问题：可能[超出上下文窗口的大小](https://cognition.ai/blog/kevin-32b?ref=blog.langchain.com)、推高成本/延迟，或降低智能体表现。Drew Breunig [很好地概述了](https://www.dbreunig.com/2025/06/22/how-contexts-fail-and-how-to-fix-them.html?ref=blog.langchain.com)更长上下文造成性能问题的若干具体方式，包括：

- [上下文投毒：幻觉进入上下文](https://www.dbreunig.com/2025/06/22/how-contexts-fail-and-how-to-fix-them.html?ref=blog.langchain.com#context-poisoning)
- [上下文分心：上下文压倒训练内容](https://www.dbreunig.com/2025/06/22/how-contexts-fail-and-how-to-fix-them.html?ref=blog.langchain.com#context-distraction)
- [上下文混淆：多余上下文影响回答](https://www.dbreunig.com/2025/06/22/how-contexts-fail-and-how-to-fix-them.html?ref=blog.langchain.com#context-confusion)
- [上下文冲突：上下文的各部分相互矛盾](https://www.dbreunig.com/2025/06/22/how-contexts-fail-and-how-to-fix-them.html?ref=blog.langchain.com#context-clash)
![](https://cdn.prod.website-files.com/65c81e88c254bb0f97633a71/69cbaaa8d3aab32815f859e0_image-3.png)

工具调用产生的上下文会跨多个智能体回合累积

考虑到这一点，[Cognition](https://cognition.ai/blog/dont-build-multi-agents?ref=blog.langchain.com) 指出了上下文工程的重要性：

> *“上下文工程”……实际上是构建 AI 智能体的工程师的头号工作。*

[Anthropic](https://www.anthropic.com/engineering/built-multi-agent-research-system?ref=blog.langchain.com) 也清楚地说明了这一点：

> *智能体常进行跨越数百回合的对话，需要细致的上下文管理策略。*

那么，人们今天如何应对这一挑战？我们把智能体上下文工程的常见策略分为四类——**写入、选择、压缩与隔离**——并通过评述一些流行智能体产品和论文给出每类示例。随后说明 LangGraph 如何被设计来支持它们！

![](https://cdn.prod.website-files.com/65c81e88c254bb0f97633a71/69cbaaa8d3aab32815f859f4_image-4.png)

上下文工程的通用类别

## 写入上下文

*写入上下文，是指将信息保存在上下文窗口外，以帮助智能体完成任务。*

**草稿板**

人类解决任务时会做笔记，并为将来相关任务记住事情。智能体也正在获得这些能力！通过“[草稿板](https://www.anthropic.com/engineering/claude-think-tool?ref=blog.langchain.com)”记笔记，是在智能体执行任务时持久化信息的一种方法。其思想是把信息保存在上下文窗口之外，让智能体仍能使用它。[Anthropic 的多智能体研究者](https://www.anthropic.com/engineering/built-multi-agent-research-system?ref=blog.langchain.com)展示了一个清晰示例：

> *LeadResearcher 首先思考方法，并把计划保存到 Memory 中以持久化上下文；因为一旦上下文窗口超过 200,000 token 就会被截断，保留计划很重要。*

草稿板可以用几种不同方式实现。它们可以只是一个[工具调用](https://www.anthropic.com/engineering/claude-think-tool?ref=blog.langchain.com)，用来[写入文件](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem?ref=blog.langchain.com)。它们也可以是运行时[状态对象](https://langchain-ai.github.io/langgraph/concepts/low_level/?ref=blog.langchain.com#state)中的一个字段，在会话期间持久存在。无论哪种方式，草稿板都让智能体保存有用信息，帮助完成任务。

**记忆**

草稿板帮助智能体在给定会话（或[线程](https://langchain-ai.github.io/langgraph/concepts/persistence/?ref=blog.langchain.com#threads)）内解决任务，但有时智能体也会受益于跨*多个*会话记住事情！[Reflexion](https://arxiv.org/abs/2303.11366?ref=blog.langchain.com) 引入了每次智能体回合后反思、并复用这些自生成记忆的思想。[Generative Agents](https://ar5iv.labs.arxiv.org/html/2304.03442?ref=blog.langchain.com) 则从过往智能体反馈的集合中，定期合成记忆。

![](https://cdn.prod.website-files.com/65c81e88c254bb0f97633a71/69cbaaa8d3aab32815f859f1_image-5.png)

LLM 可用于更新或创建记忆

这些概念已进入 [ChatGPT](https://help.openai.com/en/articles/8590148-memory-faq?ref=blog.langchain.com)、[Cursor](https://forum.cursor.com/t/0-51-memories-feature/98509?ref=blog.langchain.com) 和 [Windsurf](https://docs.windsurf.com/windsurf/cascade/memories?ref=blog.langchain.com) 等流行产品；它们都有基于用户—智能体交互、自动生成可跨会话持久化的长期记忆的机制。

## 选择上下文

*选择上下文，是指将其拉入上下文窗口，以帮助智能体完成任务。*

**草稿板**

从草稿板选择上下文的机制取决于草稿板如何实现。若它是一个[工具](https://www.anthropic.com/engineering/claude-think-tool?ref=blog.langchain.com)，智能体只需发出工具调用即可读取。若它是智能体运行时状态的一部分，开发者就可以选择每一步向智能体暴露哪些状态部分。这为在后续回合中向 LLM 暴露草稿板上下文提供了细粒度控制。

**记忆**

如果智能体能够保存记忆，也需要能选择与正在执行任务相关的记忆。这有多种用途。智能体可能选择 few-shot 示例（[情节性](https://langchain-ai.github.io/langgraph/concepts/memory/?ref=blog.langchain.com#memory-types)[记忆](https://arxiv.org/pdf/2309.02427?ref=blog.langchain.com)）作为期望行为的示例，选择指令（[程序性](https://langchain-ai.github.io/langgraph/concepts/memory/?ref=blog.langchain.com#memory-types)[记忆](https://arxiv.org/pdf/2309.02427?ref=blog.langchain.com)）来引导行为，或选择事实（[语义性](https://langchain-ai.github.io/langgraph/concepts/memory/?ref=blog.langchain.com#memory-types)[记忆](https://arxiv.org/pdf/2309.02427?ref=blog.langchain.com)）作为任务相关上下文。

![](https://cdn.prod.website-files.com/65c81e88c254bb0f97633a71/69cbaaa8d3aab32815f859e6_image-6.png)

一个挑战是确保选择到相关记忆。一些流行智能体只使用一组*始终*被拉入上下文的狭窄文件。例如，许多编码智能体使用特定文件保存指令（“程序性”记忆），有时也保存示例（“情节性”记忆）。Claude Code 使用 [`CLAUDE.md`](http://claude.md/?ref=blog.langchain.com)。[Cursor](https://docs.cursor.com/context/rules?ref=blog.langchain.com) 和 [Windsurf](https://windsurf.com/editor/directory?ref=blog.langchain.com) 使用规则文件。

但若智能体要存储由事实和/或关系构成的更大[集合](https://langchain-ai.github.io/langgraph/concepts/memory/?ref=blog.langchain.com#collection)（例如[语义性](https://langchain-ai.github.io/langgraph/concepts/memory/?ref=blog.langchain.com#memory-types)记忆），选择就更难。[ChatGPT](https://help.openai.com/en/articles/8590148-memory-faq?ref=blog.langchain.com) 是一个存储并从大量用户专属记忆中选择内容的流行产品示例。

嵌入和/或用于记忆索引的[知识](https://arxiv.org/html/2501.13956v1?ref=blog.langchain.com#:~:text=In%20Zep%2C%20memory%20is%20powered,subgraph%2C%20and%20a%20community%20subgraph)[图谱](https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/?ref=blog.langchain.com#:~:text=changes%20since%20updates%20can%20trigger,and%20holistic%20memory%20for%20agentic)常被用于辅助选择。不过，记忆选择仍具挑战。在 AIEngineer World’s Fair， [Simon Willison 分享了](https://simonwillison.net/2025/Jun/6/six-months-in-llms/?ref=blog.langchain.com)一个选择出错的例子：ChatGPT 从记忆中取出他的地理位置，并意外将其注入请求生成的图像。这类意外或不受欢迎的记忆检索，会让一些用户感到上下文窗口“*不再属于他们*”！

**工具**

智能体使用工具，但若提供的工具过多，它们可能会不堪重负。这往往是因为工具描述彼此重叠，使模型困惑该使用哪个工具。一种方法是[将 RAG（检索增强生成）应用于工具描述](https://arxiv.org/abs/2410.14594?ref=blog.langchain.com)，以便只获取与任务最相关的工具。一些[近期论文](https://arxiv.org/abs/2505.03275?ref=blog.langchain.com)显示，这可将工具选择准确率提高 3 倍。

**知识**

[RAG](https://github.com/langchain-ai/rag-from-scratch?ref=blog.langchain.com) 是一个丰富主题，也是[上下文工程的核心挑战](https://x.com/_mohansolo/status/1899630246862966837?ref=blog.langchain.com)。编码智能体是大规模生产环境中 RAG 的最佳示例之一。Windsurf 的 Varun 很好地概括了其中一些挑战：

> *代码索引 ≠ 上下文检索……\[我们在做索引和嵌入搜索……\[使用\] AST 解析代码，并按语义有意义的边界分块……随着代码库规模增长，嵌入搜索作为检索启发式会变得不可靠……我们必须依赖 grep/文件搜索、基于知识图谱的检索，以及……按相关性对\[上下文\]排序的重排步骤等技术组合。*

## 压缩上下文

*压缩上下文，是指仅保留完成任务所需的 token。*

**上下文摘要**

智能体交互可能跨越[数百回合](https://www.anthropic.com/engineering/built-multi-agent-research-system?ref=blog.langchain.com)，并使用 token 密集型工具调用。摘要是应对这些挑战的常见方式之一。如果你使用过 Claude Code，应该见过它的实际运行。Claude Code 在超过上下文窗口 95% 后运行“[自动压缩](https://docs.anthropic.com/en/docs/claude-code/costs?ref=blog.langchain.com)”，并会概述用户—智能体交互的完整轨迹。这类跨[智能体轨迹](https://langchain-ai.github.io/langgraph/concepts/memory/?ref=blog.langchain.com#manage-short-term-memory)的压缩可使用[递归式](https://arxiv.org/pdf/2308.15022?ref=blog.langchain.com#:~:text=the%20retrieved%20utterances%20capture%20the,based%203)或[分层式](https://alignment.anthropic.com/2025/summarization-for-monitoring/?ref=blog.langchain.com#:~:text=We%20addressed%20these%20issues%20by,of%20our%20computer%20use%20capability)等不同策略。

![](https://cdn.prod.website-files.com/65c81e88c254bb0f97633a71/69cbaaa8d3aab32815f859fd_image-7.png)

可以应用摘要的一些位置

在智能体设计的特定点[加入摘要](https://github.com/langchain-ai/open_deep_research/blob/e5a5160a398a3699857d00d8569cb7fd0ac48a4f/src/open_deep_research/utils.py?ref=blog.langchain.com#L1407)也很有用。例如，它可用于后处理某些工具调用（如 token 密集型搜索工具）。另一个例子是，[Cognition](https://cognition.ai/blog/dont-build-multi-agents?ref=blog.langchain.com#a-theory-of-building-long-running-agents)提到在智能体—智能体边界处进行摘要，以减少知识交接时的 token。若需捕捉特定事件或决策，摘要可能是一项挑战。[Cognition](https://cognition.ai/blog/dont-build-multi-agents?ref=blog.langchain.com#a-theory-of-building-long-running-agents)为此使用微调模型，这凸显此步骤可能需要投入多少工作。

**上下文裁剪**

摘要通常使用 LLM 提炼最相关的上下文片段，而裁剪则常常只是筛选，或如 Drew Breunig 所说，对上下文进行“[修枝](https://www.dbreunig.com/2025/06/26/how-to-fix-your-context.html?ref=blog.langchain.com)”。它可以使用硬编码启发式，例如从列表中移除[较早消息](https://python.langchain.com/docs/how_to/trim_messages/?ref=blog.langchain.com)。Drew 还提到 [Provence](https://arxiv.org/abs/2501.16214?ref=blog.langchain.com)，这是一个用于问答的训练型上下文修剪器。

## 隔离上下文

*隔离上下文，是指将其拆分，以帮助智能体完成任务。*

**多智能体**

隔离上下文最流行的方式之一，是将其拆分给子智能体。OpenAI [Swarm](https://github.com/openai/swarm?ref=blog.langchain.com) 库的一项动机是[关注点分离](https://openai.github.io/openai-agents-python/ref/agent/?ref=blog.langchain.com)，即智能体团队可以处理特定子任务。每个智能体都有一组特定工具、指令和自己的上下文窗口。

![](https://cdn.prod.website-files.com/65c81e88c254bb0f97633a71/69cbaaa8d3aab32815f85a00_image-8.png)

将上下文拆分给多个智能体

Anthropic 的[多智能体研究者](https://www.anthropic.com/engineering/built-multi-agent-research-system?ref=blog.langchain.com)为此提供了理由：拥有隔离上下文的多个智能体优于单智能体，很大程度上是因为每个子智能体的上下文窗口可以分配给更狭窄的子任务。正如该博文所说：

> *\[子智能体\]“在各自的上下文窗口中并行运行，同时探索问题的不同方面。”*

当然，多智能体的挑战包括 token 用量（Anthropic 报告称，例如可能比聊天多用[15 倍 token](https://www.anthropic.com/engineering/built-multi-agent-research-system?ref=blog.langchain.com)）、为规划子智能体工作而细致进行[提示词工程](https://www.anthropic.com/engineering/built-multi-agent-research-system?ref=blog.langchain.com)，以及子智能体协调。

**通过环境隔离上下文**

HuggingFace 的[深度研究者](https://huggingface.co/blog/open-deep-research?ref=blog.langchain.com#:~:text=From%20building%20,it%20can%20still%20use%20it)展示了另一个有趣的上下文隔离示例。大多数智能体使用[工具调用 API](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview?ref=blog.langchain.com)，后者返回 JSON 对象（工具参数），可传给工具（例如搜索 API）以获得工具反馈（例如搜索结果）。HuggingFace 使用 [CodeAgent](https://huggingface.co/papers/2402.01030?ref=blog.langchain.com)，它输出包含所需工具调用的代码。随后代码在[沙盒](https://e2b.dev/?ref=blog.langchain.com)中运行。来自工具调用的选定上下文（如返回值）随后被传回 LLM。

![](https://cdn.prod.website-files.com/65c81e88c254bb0f97633a71/69cbaaa8d3aab32815f859fa_image-9.png)

沙盒可以将上下文与 LLM 隔离。

这让上下文能在环境中与 LLM 隔离。Hugging Face 指出，这尤其适合隔离 token 密集型对象：

> *\[代码智能体能够\]“更好地处理状态……需要保存这张图像/音频/其他内容以供稍后使用？没问题，只需将其赋值给状态中的变量* [*，随后即可使用\]*](https://deepwiki.com/search/i-am-wondering-if-state-that-i_0e153539-282a-437c-b2b0-d2d68e51b873?ref=blog.langchain.com)*。”*

**状态**

值得指出的是，智能体运行时的[状态对象](https://langchain-ai.github.io/langgraph/concepts/low_level/?ref=blog.langchain.com#state)也是隔离上下文的好方法。它可达到与沙盒相同的目的。状态对象可使用带有字段的[模式](https://langchain-ai.github.io/langgraph/concepts/low_level/?ref=blog.langchain.com#schema)设计，上下文可以写入这些字段。模式中的一个字段（例如 `messages`）可以在智能体每个回合向 LLM 暴露，而模式会在其他字段中隔离信息，以便更有选择地使用。

## 使用 LangSmith / LangGraph 进行上下文工程

那么，如何应用这些理念？开始前，有两个基础要素很有帮助。第一，确保你有办法[查看数据](https://hamel.dev/blog/posts/evals/?ref=blog.langchain.com)并跟踪智能体的 token 用量。这有助于判断最值得投入上下文工程精力的位置。[LangSmith](https://docs.smith.langchain.com/?ref=blog.langchain.com) 很适合进行智能体[追踪/可观测性](https://docs.smith.langchain.com/observability?ref=blog.langchain.com)，并提供很好的实现方式。第二，确保有简单方法测试上下文工程会损害还是改善智能体表现。LangSmith 支持[智能体评估](https://docs.smith.langchain.com/evaluation/tutorials/agents?ref=blog.langchain.com)，可测试任何上下文工程工作的影响。

**写入上下文**

LangGraph 的设计同时支持线程范围的[短期](https://langchain-ai.github.io/langgraph/concepts/memory/?ref=blog.langchain.com#short-term-memory)与[长期记忆](https://langchain-ai.github.io/langgraph/concepts/memory/?ref=blog.langchain.com#long-term-memory)。短期记忆使用[检查点](https://langchain-ai.github.io/langgraph/concepts/persistence/?ref=blog.langchain.com)在智能体所有步骤中持久保存[智能体状态](https://langchain-ai.github.io/langgraph/concepts/low_level/?ref=blog.langchain.com#state)。这作为“草稿板”极其有用：你可以把信息写入状态，并在智能体轨迹的任何步骤取回它。

LangGraph 的长期记忆让你能让智能体跨*许多会话*持久保存上下文。它很灵活，既可保存小型[文件集](https://langchain-ai.github.io/langgraph/concepts/memory/?ref=blog.langchain.com#profile)（如用户配置或规则），也可保存更大的记忆[集合](https://langchain-ai.github.io/langgraph/concepts/memory/?ref=blog.langchain.com#collection)。此外，[LangMem](https://langchain-ai.github.io/langmem/?ref=blog.langchain.com)提供了大量有用抽象，以帮助进行 LangGraph 记忆管理。

**选择上下文**

在 LangGraph 智能体的每个节点（步骤）中，都可以获取[状态](https://langchain-ai.github.io/langgraph/concepts/low_level/?ref=blog.langchain.com#state)。这让你能精细控制每个智能体步骤向 LLM 呈现哪些上下文。

此外，LangGraph 的长期记忆可在每个节点中访问，并支持各种检索类型（例如获取文件，以及对记忆集合进行[基于嵌入的检索）。](https://langchain-ai.github.io/langgraph/cloud/reference/cli/?ref=blog.langchain.com#adding-semantic-search-to-the-store)如需长期记忆概览，可参阅我们的 [Deeplearning.ai 课程](https://www.deeplearning.ai/short-courses/long-term-agentic-memory-with-langgraph/?ref=blog.langchain.com)。如需将记忆用于特定智能体的入口，可参阅 [Ambient Agents](https://academy.langchain.com/courses/ambient-agents?ref=blog.langchain.com) 课程。该课程展示如何在一个能管理电子邮件、并从你的反馈中学习的长时运行智能体中使用 LangGraph 记忆。

![](https://cdn.prod.website-files.com/65c81e88c254bb0f97633a71/69cbaaa8d3aab32815f859f7_image-10.png)

带有用户反馈和长期记忆的电子邮件智能体

对于工具选择，[LangGraph Bigtool](https://github.com/langchain-ai/langgraph-bigtool?ref=blog.langchain.com) 库是对工具描述应用语义搜索的好方法。它有助于在使用大量工具集合时，为任务选择最相关的工具。最后，我们有若干[教程和视频](https://langchain-ai.github.io/langgraph/tutorials/rag/langgraph_agentic_rag/?ref=blog.langchain.com)，展示如何将各种 RAG 与 LangGraph 一起使用。

**压缩上下文**

由于 LangGraph [是低层编排框架](https://blog.langchain.com/how-to-think-about-agent-frameworks/)，你可以[将智能体布置为一组节点](https://www.youtube.com/watch?v=aHCDrAbH_go&ref=blog.langchain.com)、[定义](https://blog.langchain.com/how-to-think-about-agent-frameworks/)每个节点内的逻辑，并定义一个在节点之间传递的状态对象。这种控制带来若干压缩上下文的方式。

一种常见方法是使用消息列表作为智能体状态，并借助[若干内置工具](https://langchain-ai.github.io/langgraph/how-tos/memory/add-memory/?ref=blog.langchain.com#manage-short-term-memory)，定期[概述或裁剪](https://langchain-ai.github.io/langgraph/how-tos/memory/add-memory/?ref=blog.langchain.com#manage-short-term-memory)它。不过，也可以以不同方式添加逻辑，后处理[工具调用](https://github.com/langchain-ai/open_deep_research/blob/e5a5160a398a3699857d00d8569cb7fd0ac48a4f/src/open_deep_research/utils.py?ref=blog.langchain.com#L1407)或智能体的工作阶段。你可以在特定点添加摘要节点，也可以在工具调用节点添加摘要逻辑，以压缩特定工具调用的输出。

**隔离上下文**

LangGraph 围绕[状态](https://langchain-ai.github.io/langgraph/concepts/low_level/?ref=blog.langchain.com#state)对象设计，因此你可以指定状态模式，并在智能体每步访问状态。例如，可以将工具调用的上下文存储在状态的特定字段中，在 LLM 需要该上下文之前将其隔离。除状态外，LangGraph 还支持使用沙盒隔离上下文。可参阅这个 [repo](https://github.com/jacoblee93/mini-chat-langchain?tab=readme-ov-file&ref=blog.langchain.com)，其中的 LangGraph 智能体使用 [E2B 沙盒](https://e2b.dev/?ref=blog.langchain.com)进行工具调用。还可观看这个[视频](https://www.youtube.com/watch?v=FBnER2sxt0w&ref=blog.langchain.com)，了解使用 Pyodide 的沙盒示例，其中状态可以持久保存。LangGraph 对构建多智能体架构也提供了很多支持，例如 [supervisor](https://github.com/langchain-ai/langgraph-supervisor-py?ref=blog.langchain.com) 和 [swarm](https://github.com/langchain-ai/langgraph-swarm-py?ref=blog.langchain.com) 库。可观看[这些](https://www.youtube.com/watch?v=4nZl32FwU-o&ref=blog.langchain.com)[视频](https://www.youtube.com/watch?v=JeyDrn1dSUQ&ref=blog.langchain.com)[视频](https://www.youtube.com/watch?v=B_0TNuYi56w&ref=blog.langchain.com)，了解使用 LangGraph 构建多智能体的更多细节。

## 结语

上下文工程正在成为智能体构建者应力求掌握的一门技艺。本文涵盖了如今许多流行智能体中常见的几种模式：

- *写入上下文——将其保存在上下文窗口之外，以帮助智能体完成任务。*
- *选择上下文——将其拉入上下文窗口，以帮助智能体完成任务。*
- *压缩上下文——仅保留完成任务所需的 token。*
- *隔离上下文——将其拆分，以帮助智能体完成任务。*

LangGraph 让实现上述每一项变得容易，LangSmith 则提供了测试智能体和跟踪上下文使用的简便方法。两者结合，LangGraph 与 LangGraph 可形成良性反馈循环：发现最值得应用上下文工程的机会、实现、测试并重复。
