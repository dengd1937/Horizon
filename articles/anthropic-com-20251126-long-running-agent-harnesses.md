---
title: 面向长时运行智能体的有效 harness
source_url: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
source_domain: anthropic.com
published_date: '2025-11-26'
added_date: '2026-07-16'
slug: anthropic-com-20251126-long-running-agent-harnesses
summary: Anthropic 提出初始化智能体与增量编码智能体组成的 harness，通过功能清单、进度工件、git 历史和端到端测试，让智能体可跨多个上下文窗口持续推进复杂软件任务。
tags:
- AI agents
- agent harness
- software engineering
- Anthropic
cover: https://cdn.sanity.io/images/4zrzovbb/website/32ea71b3e8e87a990f6df4c4def2b9e52815e977-2400x1260.png
---

# 面向长时运行智能体的有效 harness \ Anthropic

随着 AI 智能体能力不断增强，开发者越来越多地要求它们承担需要持续数小时、甚至数天的复杂任务。然而，让智能体在多个上下文窗口之间持续、稳定地取得进展，仍是一个开放问题。

长时运行智能体的核心难题在于：它们必须在离散的会话中工作，而每个新会话开始时都不记得此前发生了什么。可以把它想象成一个由轮班工程师组成的软件项目：每位新工程师到岗时，对前一班发生的事情毫无记忆。由于上下文窗口有限，而大多数复杂项目无法在单个窗口内完成，智能体需要一种方式来弥合编码会话之间的断层。

我们为 [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview) 开发了一套双重方案，使其能够跨越许多上下文窗口有效工作：首次运行时由**初始化智能体**设置环境；之后由**编码智能体**在每个会话中逐步推进，同时为下一次会话留下清晰的工件。随附的 [quickstart](https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding) 提供了代码示例。

## 长时运行智能体问题

Claude Agent SDK 是一个强大的通用智能体 harness，擅长编码以及其他需要模型使用工具来收集上下文、规划和执行的任务。它拥有压缩等上下文管理能力，使智能体可以在不耗尽上下文窗口的情况下处理任务。从理论上说，有了这套配置，智能体应能在任意长的时间内持续完成有价值的工作。

但仅有压缩还不够。开箱即用时，即便是像 Opus 4.5 这样处于前沿的编码模型，在 Claude Agent SDK 中跨多个上下文窗口循环运行，如果只接到“构建一个 [claude.ai](http://claude.ai/redirect/website.v1.7c94c08c-c78d-4c5d-beb1-1af29768f064) 的克隆”这类高层提示，也无法构建生产质量的 Web 应用。

Claude 的失败呈现为两种模式。第一，智能体往往试图一次做得太多——实质上想一击完成整个应用。这通常会让模型在实现途中耗尽上下文，下一次会话面对的是实现了一半且没有文档的功能。随后智能体只能猜测此前发生过什么，并花费大量时间重新让基础应用正常工作。即使使用压缩也会出现这种问题，因为压缩并不总能把完全清楚的指令交给下一位智能体。

第二种失败模式常在项目后期出现：一些功能已经完成后，后续智能体实例环顾四周，发现已有进展，便宣布任务已经完成。

这将问题拆为两部分。首先，我们需要建立一个初始环境，为某个提示所要求的*所有*功能打下基础，使智能体能够逐步、逐个功能地工作。其次，应提示每个智能体向目标取得增量进展，并在会话结束时让环境保持干净。所谓“干净状态”，是指适合合并到主分支的代码：没有重大 bug，代码有序且文档完善，并且开发者无需先清理无关混乱，就能轻松开始新功能。

在内部实验中，我们用一个两部分方案解决这些问题：

1. 初始化智能体：第一个智能体会话使用专门提示，要求模型设置初始环境：`init.sh` 脚本、记录智能体已完成内容的 claude-progress.txt 文件，以及显示新增文件的初始 git 提交。
2. 编码智能体：之后的每个会话都要求模型取得增量进展，再留下结构化更新。<sup>1</sup>

关键洞见是找到一种方法，让智能体在以全新上下文窗口启动时能迅速理解工作状态；这由 claude-progress.txt 文件与 git 历史共同实现。其灵感来自对高效软件工程师日常工作方式的理解。

## 环境管理

在更新后的 [Claude 4 提示词指南](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices#multi-context-window-workflows) 中，我们分享了多上下文窗口工作流的最佳实践，其中包括一种 harness 结构：为“第一个上下文窗口使用不同的提示词”。这个“不同提示词”要求初始化智能体设置环境，使未来的编码智能体拥有高效工作所需的全部上下文。这里我们将深入介绍这类环境的几个关键组成部分。

### 功能清单

为解决智能体试图一击完成应用，或过早认定项目完成的问题，我们提示初始化智能体编写一份全面的功能需求文件，扩展用户的初始提示。在 [claude.ai](http://claude.ai/redirect/website.v1.7c94c08c-c78d-4c5d-beb1-1af29768f064) 克隆示例中，这意味着 200 多项功能，例如“用户可以打开新聊天、输入查询、按回车，并看到 AI 回复”。这些功能一开始均标记为“失败”，使后续编码智能体能清楚了解完整功能应是什么样子。

```
{
    "category": "functional",
    "description": "New chat button creates a fresh conversation",
    "steps": [
      "Navigate to main interface",
      "Click the 'New Chat' button",
      "Verify a new conversation is created",
      "Check that chat area shows welcome state",
      "Verify conversation appears in sidebar"
    ],
    "passes": false
  }
```

我们提示编码智能体只通过改变 passes 字段的状态来编辑该文件，并使用措辞强烈的指令，例如“移除或编辑测试不可接受，因为这可能导致功能缺失或存在 bug”。经过一些实验，我们最终使用 JSON，因为相对于 Markdown 文件，模型不太可能不恰当地更改或覆盖 JSON 文件。

### 增量进展

有了这个初始环境脚手架后，编码智能体的下一次迭代会被要求一次只处理一个功能。这种增量方法对于解决智能体一次尝试做太多事情的倾向至关重要。

即使按增量方式工作，模型在改完代码后仍必须让环境保持干净状态。我们的实验发现，最能促成这一行为的方法，是要求模型用描述性的提交信息把进展提交到 git，并在进度文件中记录进展摘要。这样模型就能使用 git 回滚糟糕的代码改动，并恢复代码库可工作的状态。

这些做法还提高了效率，因为它们消除了智能体必须猜测此前发生了什么、并花时间重新让基础应用工作起来的需要。

### 测试

我们观察到的最后一个重大失败模式，是 Claude 未经恰当测试就将功能标记为完成的倾向。如果没有明确提示，Claude 往往会修改代码，甚至使用单元测试或针对开发服务器的 `curl` 命令测试，却无法识别该功能在端到端场景中并不工作。

在构建 Web 应用时，只要明确提示 Claude 使用浏览器自动化工具，并像人类用户一样完成所有测试，它通常就能很好地端到端验证功能。

![Claude 通过 Puppeteer MCP 测试 claude.ai 克隆时截取的屏幕截图。](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2Ff94c2257964fb2d623f1e81f874977ebfc0986bc-1920x1080.gif&w=3840&q=75)

Claude 通过 Puppeteer MCP 测试 claude.ai 克隆时截取的屏幕截图。

为 Claude 提供这类测试工具显著提升了性能，因为智能体能够发现并修复仅从代码本身不明显的 bug。

仍有一些问题存在，例如 Claude 的视觉能力和浏览器自动化工具的限制，使其难以识别每一种 bug。比如 Claude 无法通过 Puppeteer MCP 看见浏览器原生的 alert 模态框，因此依赖这些模态框的功能往往会更容易出错。

## 快速进入状态

完成上述设置后，每个编码智能体都会被提示执行一系列步骤来熟悉环境；其中一些很基础，但仍很有帮助：

1. *运行 `pwd`，查看自己正在工作的目录。你只能编辑该目录内的文件。*
2. *阅读 git 日志和进度文件，了解最近完成了什么工作。*
3. *阅读功能清单文件，选择优先级最高、尚未完成的功能开始处理。*

这种方法能在每个会话中为 Claude 节省一些 token，因为它不必自行摸索如何测试代码。还应要求初始化智能体写一个能运行开发服务器的 init.sh 脚本，并在实现新功能前先进行基本端到端测试。

在 claude.ai 克隆案例中，这意味着智能体始终启动本地开发服务器，并使用 Puppeteer MCP 开启新聊天、发送消息和接收回复。这样 Claude 能快速识别应用是否被遗留在损坏状态，并立即修复现有 bug。若智能体反而先开始实现一个新功能，问题很可能变得更糟。

在具备上述条件后，一个典型会话会以如下助手消息开始：

```
[Assistant] I'll start by getting my bearings and understanding the current state of the project.
[Tool Use] <bash - pwd>
[Tool Use] <read - claude-progress.txt>
[Tool Use] <read - feature_list.json>
[Assistant] Let me check the git log to see recent work.
[Tool Use] <bash - git log --oneline -20>
[Assistant] Now let me check if there's an init.sh script to restart the servers.
<Starts the development server>
[Assistant] Excellent! Now let me navigate to the application and verify that some fundamental features are still working.
<Tests basic functionality>
[Assistant] Based on my verification testing, I can see that the fundamental functionality is working well. The core chat features, theme switching, conversation loading, and error handling are all functioning correctly. Now let me review the tests.json file more comprehensively to understand what needs to be implemented next.
<Starts work on a new feature>
```

智能体失败模式与解决方案

| **问题** | **初始化智能体行为** | **编码智能体行为** |
| --- | --- | --- |
| Claude 过早宣布整个项目胜利完成。 | 设置功能清单文件：基于输入规格建立一个结构化 JSON 文件，列出端到端功能描述。 | 会话开始时读取功能清单文件；选择一个功能开始处理。 |
| Claude 让环境遗留 bug 或未记录的进展。 | 写入初始 git 仓库与进度说明文件。 | 会话开始时读取进度说明和 git 提交日志，并在开发服务器上运行基本测试以发现未记录的 bug；会话结束时写入 git 提交和进度更新。 |
| Claude 过早将功能标记为完成。 | 设置功能清单文件。 | 自行验证所有功能；只有经过仔细测试后才将功能标记为“通过”。 |
| Claude 必须花时间弄清如何运行应用。 | 编写可以运行开发服务器的 `init.sh` 脚本。 | 会话开始时读取 `init.sh`。 |

总结长时运行 AI 智能体四种常见失败模式及其解决方案。

## 后续工作

这项研究展示了一组可行的长时运行智能体 harness 方案，使模型能跨越许多上下文窗口取得增量进展。不过，仍有一些开放问题。

最值得注意的是，我们仍不清楚单个通用编码智能体是否能在跨上下文工作时表现最佳，或多智能体架构是否能带来更好性能。测试智能体、质量保证智能体或代码清理智能体等专门智能体，似乎有理由在软件开发生命周期的子任务上做得更好。

此外，该演示针对全栈 Web 应用开发进行了优化。未来方向是把这些发现推广到其他领域。其中部分或全部经验，很可能可用于科学研究或金融建模等需要长时运行智能体完成的任务。

### 致谢

本文由 Justin Young 撰写。特别感谢 David Hershey、Prithvi Rajasakeran、Jeremy Hadfield、Naia Bouscal、Michael Tingley、Jesse Mu、Jake Eaton、Marius Buleandara、Maggie Vo、Pedram Navid、Nadine Yasser 和 Alex Notov 的贡献。

本工作体现了 Anthropic 多个团队的集体努力；他们让 Claude 能够安全地开展长时程自主软件工程，尤其是 code RL 和 Claude Code 团队。欢迎有意参与的候选人申请 [anthropic.com/careers](http://anthropic.com/careers)。

1\. 此处我们仅因这些智能体具有不同的初始用户提示，而将它们称作不同智能体；系统提示词、工具集和整体智能体 harness 则完全相同。
