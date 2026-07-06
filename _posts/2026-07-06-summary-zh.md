---
layout: default
title: "Horizon Summary: 2026-07-06 (ZH)"
date: 2026-07-06
lang: zh
---

> 从 5 条内容中筛选出 5 条重要资讯。

---

1. [《命令与征服：将军》被移植到 iOS，但大部分工作来自上游项目](#item-1) ⭐️ 7.0/10
2. [Baoyu-design Skill 现通过 Fable 5 支持 PPT 动画](#item-2) ⭐️ 7.0/10
3. [GLM-5.2 现可通过 Hugging Face 在 Claude Code 中使用](#item-3) ⭐️ 7.0/10
4. [AI 与自动化可能淘汰 Web 基础设施团队](#item-4) ⭐️ 6.0/10
5. [Karpathy 分享 Fable 的 60 多个 3D 提示演示](#item-5) ⭐️ 6.0/10

---

<a id="item-1"></a>
## [《命令与征服：将军》被移植到 iOS，但大部分工作来自上游项目](https://x.com/dotey/status/2073541964318883941) ⭐️ 7.0/10

开发者 Ammaar Reshi 声称使用 Fable 5 和 Claude Code 将《命令与征服：将军：绝命时刻》移植到了 iPhone 和 iPad 上。但社区分析显示，仓库中约 2000 次提交中只有最近 19 次来自 Reshi，绝大多数来自 GeneralsX 项目。Fable 5 工具负责了最后的 iOS 集成，包括 DXVK 适配、MoltenVK 框架集成和触控系统重新设计。 这则新闻凸显了使用 Claude Code 和 Fable 5 等 AI 辅助工具加速游戏移植的趋势，可能将数月的工作缩短至数小时。但它也强调了正确归功于上游开源项目的重要性，因为核心的跨平台工作已由 GeneralsX 社区完成。该移植展示了经典 RTS 游戏可以在移动设备上原生运行并支持触控操作，为其他老游戏开辟了可能性。 该移植运行的是原生编译为 ARM64 的 2003 年引擎，无需模拟器。它支持战役、遭遇战和将军挑战模式，并配有专为 RTS 设计的触控操作。仓库已开源，但不包含游戏资源。技术栈包括 DXVK（DirectX 到 Vulkan 的转换）和 MoltenVK（Vulkan 到 Metal 的转换），使游戏能通过 Metal 在 iOS 上运行。

twitter · dotey · 7月4日 22:58 · [原文链接](https://x.com/dotey/status/2073541964318883941)

**背景**: 《命令与征服：将军》是 EA 于 2003 年发布的即时战略游戏。2025 年，EA 以 GPL v3 许可证开源了源代码，推动了社区移植工作。由 fbraz3 领导的 GeneralsX 项目自 2025 年 2 月起致力于跨平台移植，积累了约 2000 次提交。Fable 5 是一个游戏移植工具，使用 AI（Claude Code）自动化部分移植过程。DXVK 将 DirectX 9/10/11 转换为 Vulkan，MoltenVK 将 Vulkan 转换为 Apple 的 Metal API，两者结合使 Windows 游戏能在 macOS/iOS 上运行。

**社区讨论**: X（原 Twitter）上的社区讨论指出，大部分工作由 GeneralsX 项目完成，Reshi 的贡献只是最后的 iOS 集成。这引发了关于正确归功和 AI 工具在移植中作用的讨论。一些人称赞 iOS 移植的技术成就，而另一些人则强调核心工作已经完成。

**标签**: `#game porting`, `#iOS`, `#RTS`, `#open source`, `#reverse engineering`

---

<a id="item-2"></a>
## [Baoyu-design Skill 现通过 Fable 5 支持 PPT 动画](https://x.com/dotey/status/2073286406558949828) ⭐️ 7.0/10

Baoyu-design Skill 已更新，支持 PPT 动画导出，克服了之前 PptxGenJS 不支持动画的限制。该更新利用 Claude Fable 5 对 PPTX XML 格式的深入理解，生成可在 Keynote 或 PowerPoint 中预览的动画幻灯片。 此更新通过支持动画幻灯片导出，显著提升了 AI 生成演示文稿的实用性，这是许多用户要求的功能。它展示了 Claude Fable 5 在复杂文档生成任务中的实际价值，可能推动 AI 辅助演示文稿创作的普及。 动画导出通过先生成基于 HTML 的 PPT，然后使用 PptxGenJS 转换为 PPTX 实现，但现在由 Fable 5 处理动画 XML。开发者指出，虽然动画细节上有些小出入，但常用的动画效果良好。该 Skill 可作为本地 Agent Skill 用于 Cursor、Claude Code 和 Claude Desktop 等工具。

twitter · dotey · 7月4日 06:02 · [原文链接](https://x.com/dotey/status/2073286406558949828)

**背景**: PptxGenJS 是一个流行的 JavaScript 库，用于以编程方式创建 PowerPoint 演示文稿，但不支持动画。Claude Fable 5 是 Anthropic 的最新模型，以其强大的代码生成和多阶段代理能力而闻名。Baoyu-design Skill 将 Claude 的设计能力打包为可移植的 Agent Skill，支持本地 AI 辅助的 UI 原型和演示文稿生成。

**标签**: `#PPT`, `#animation`, `#Fable 5`, `#AI`, `#tool`

---

<a id="item-3"></a>
## [GLM-5.2 现可通过 Hugging Face 在 Claude Code 中使用](https://x.com/Zai_org/status/2073449055334838362) ⭐️ 7.0/10

Zai.org 的最新旗舰模型 GLM-5.2 现可通过 Hugging Face Inference Providers 在 Claude Code 中选择使用。这一集成使开发者无需切换平台，即可直接在 Anthropic 的编码代理中使用该开放模型。 此举显著降低了开发者在实际编码工作流中尝试前沿开放模型的门槛。它标志着专有编码代理与开放模型生态系统之间互操作的趋势，可能加速开放模型在生产中的采用。 GLM-5.2 支持 100 万 token 的上下文窗口，擅长长周期任务（包括编码）。该集成使用 Hugging Face Inference Providers（将多个推理合作伙伴统一到单个兼容 OpenAI 的端点下）以及 hf-claude 工具。目前尚未公布通过此集成使用 GLM-5.2 的定价细节。

twitter · Zai_org · 7月4日 16:49 · [原文链接](https://x.com/Zai_org/status/2073449055334838362)

**背景**: Claude Code 是 Anthropic 开发的 AI 编码代理，可通过终端、IDE 或浏览器读取代码库、编辑文件并运行命令。Hugging Face Inference Providers 提供统一 API，可访问来自多个提供商的数千个模型。GLM-5.2 是 Zai.org 的开源模型，是 GLM-5.1 的后续版本，在长周期任务性能上有所提升。

**标签**: `#GLM-5.2`, `#Claude Code`, `#Hugging Face`, `#open models`, `#developer tools`

---

<a id="item-4"></a>
## [AI 与自动化可能淘汰 Web 基础设施团队](https://x.com/dotey/status/2073749390368395744) ⭐️ 6.0/10

开发者@dotey 认为，由于 AI 和自动化，大部分公司不再需要专门的 Web 基础设施团队。他建议专注于 CI/CD 技能、拥抱 AI 友好的开源项目，并将设计系统简化为一个 design.md 文件。 这一观点反映了 AI 和自动化正在重塑软件工程角色的趋势，可能减少对专业基础设施团队的需求。如果被广泛采纳，可能导致更扁平化的团队结构，并增加对自动化流水线和 AI 辅助工具的依赖。 该推文引用了另一位开发者@i5ting 的抱怨，称 AI 打乱了传统的 Web 基础设施团队结构。@dotey 建议，像 CI/CD 和 AI 友好的开源项目这样的技能比维护单独的基础设施团队更有价值。将设计系统简化为 design.md 文件的提议与新兴实践一致，即 AI 代理读取 markdown 规范来生成代码。

twitter · dotey · 7月5日 12:42 · [原文链接](https://x.com/dotey/status/2073749390368395744)

**背景**: Web 基础设施团队传统上负责管理服务器、部署流水线和开发者工具，以确保 Web 应用的可靠性和可扩展性。CI/CD（持续集成/持续交付）自动化了构建、测试和部署，减少了人工开销。AI 工具如代码生成器和自动化测试越来越能够处理以前需要专门团队完成的任务。design.md 文件的概念受 Google 的 AGENTS.md 启发，通过单个 markdown 文件为 AI 编码代理定义设计系统。

**标签**: `#web infrastructure`, `#AI`, `#CI/CD`, `#automation`, `#software engineering`

---

<a id="item-5"></a>
## [Karpathy 分享 Fable 的 60 多个 3D 提示演示](https://x.com/karpathy/status/2073496962566164990) ⭐️ 6.0/10

Andrej Karpathy 分享了一段 45 分钟的视频合集，展示了使用 Fable 平台创建的 60 多个具有挑战性的 3D 提示演示。提示词在后续帖子中提供，以便他人复现结果。 这凸显了从文本提示生成 AI 驱动的 3D 内容的能力日益增强，可能使 3D 建模对创作者更加普及。Karpathy 的认可将注意力引向 Fable 平台以及提示工程在 3D 领域的潜力。 该视频时长 45 分钟，包含 60 多个演示，展示了创作者能找到的最难的 3D 提示。提示词在另一篇帖子中分享，使社区能够测试并在此基础上进行构建。Fable 平台似乎是一个用于 AI 和 3D 内容创作的模拟环境。

twitter · karpathy · 7月4日 19:59 · [原文链接](https://x.com/karpathy/status/2073496962566164990)

**背景**: Fable 是一家以创建虚拟生命和 AI 驱动模拟而闻名的工作室。其平台“The Simulation”允许用户在丰富的 3D 环境中编程、训练和与 AI 交互。提示工程涉及编写特定的文本输入以引导 AI 模型产生期望的输出，而此演示合集展示了用于 3D 生成的高级技术。

**标签**: `#3D`, `#AI`, `#prompts`, `#demos`

---