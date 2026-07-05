---
layout: default
title: "Horizon Summary: 2026-07-05 (ZH)"
date: 2026-07-05
lang: zh
---

> 从 8 条内容中筛选出 7 条重要资讯。

---

1. [AI 代理发现 curl 漏洞，Mythos 未能检出](#item-1) ⭐️ 8.0/10
2. [Sergey Brin 谈谷歌的 AGI 战略与编程代理](#item-2) ⭐️ 8.0/10
3. [《将军》iOS 移植：Fable 5 还是 GeneralsX？](#item-3) ⭐️ 7.0/10
4. [Baoyu-Design 技能现通过 Fable 5 支持 PPT 动画](#item-4) ⭐️ 7.0/10
5. [AI 时代职业建议：领域专长胜于纯编程](#item-5) ⭐️ 7.0/10
6. [GLM-5.2 现可通过 Hugging Face 在 Claude Code 中使用](#item-6) ⭐️ 7.0/10
7. [Karpathy 分享 Fable 的 60 多个 3D 提示演示](#item-7) ⭐️ 6.0/10

---

<a id="item-1"></a>
## [AI 代理发现 curl 漏洞，Mythos 未能检出](https://x.com/dotey/status/2072941568625906125) ⭐️ 8.0/10

名为阿图因 AI 的代理在 curl 中发现了一个新的中危漏洞（CVE-2026-9079），而 Mythos 模型未能发现该漏洞。该漏洞已于 2026 年 6 月 24 日在 curl 8.21.0 版本中修复。这一结果是在 CyberGym 基准测试中对比两个系统时取得的。 这表明，在漏洞发现等特定网络安全任务上，专门的 AI 代理可以胜过 Mythos 这样的通用模型。它凸显了 AI 安全工具中任务特定设计的重要性，并提示可能需要代理与模型的组合才能实现全面的安全分析。 漏洞 CVE-2026-9079 是一个过时代理密码泄露问题（CWE-522），严重等级为中危。阿图因 AI 是一个专为漏洞挖掘设计的代理，而 Mythos 是 Anthropic 开发的通用大语言模型。由于 Mythos 不公开访问，对比存在局限，且阿图因 AI 在其设计目标之外的任务上可能表现不佳。

twitter · dotey · 7月3日 07:12 · [原文链接](https://x.com/dotey/status/2072941568625906125)

**背景**: CyberGym 是一个基准测试平台，利用来自 188 个软件项目的 1507 个历史漏洞来评估 AI 代理在真实网络安全任务上的表现。Mythos 是 Anthropic 开发的高级 AI 模型，以发现软件漏洞的能力著称，但因安全顾虑未公开发布。curl 是一个广泛使用的命令行工具和库，用于通过 URL 传输数据，其漏洞可能影响众多系统。

**社区讨论**: 讨论中包含一条评论，称赞作者清晰解释复杂话题的能力。作者指出，阿图因 AI 和 Mythos 并非同类系统（代理 vs 模型），因此直接比较并不简单。

**标签**: `#AI`, `#cybersecurity`, `#vulnerability`, `#curl`, `#CVE`

---

<a id="item-2"></a>
## [Sergey Brin 谈谷歌的 AGI 战略与编程代理](https://x.com/dotey/status/2072904438386208939) ⭐️ 8.0/10

谷歌联合创始人 Sergey Brin 在 AGI House 参加了一场问答，讨论了谷歌重新将编程代理作为最高优先级之一、他将 AGI 理解为能够自我改进的 AI，以及世界模型的重要性。他承认过去在大模型上落后，但对 Gemini 的进展表示信心，同时指出竞争对手在编程任务上进步迅速。 这提供了来自关键人物的罕见内部视角，揭示了编程代理和自我改进的 AI 现已成为谷歌 AGI 路线图的核心。这标志着竞争格局的转变——谷歌在最初落后后加倍投入编程领域，并凸显了科技巨头之间实现 AGI 的持续竞赛。 Brin 表示谷歌已将编程列为最高优先级之一，并承认他们本应更早关注这一领域。他指出 Gemini Flash 在交互式快速迭代方面具有速度优势，而其他模型在长时间深度编程任务上表现更好。他还强调 AGI 应被定义为自我改进而非单纯完成任务，并且世界模型对于 AI 与物理世界互动至关重要。

twitter · dotey · 7月3日 04:45 · [原文链接](https://x.com/dotey/status/2072904438386208939)

**背景**: AGI House 是由 Rocky Yu 于 2023 年创立的社区，致力于推动 AI 研究和应用。世界模型是构建环境内部表征以预测行动结果的 AI 系统，对机器人和自主系统至关重要。编程代理是能够自主编写、调试和优化代码的 AI 工具，已成为谷歌、OpenAI 和 Anthropic 等 AI 公司的关键竞争领域。

**标签**: `#Google`, `#AGI`, `#coding agents`, `#Sergey Brin`, `#Gemini`

---

<a id="item-3"></a>
## [《将军》iOS 移植：Fable 5 还是 GeneralsX？](https://x.com/dotey/status/2073541964318883941) ⭐️ 7.0/10

一位名为 Reshi 的开发者声称借助 Fable 5 将 2003 年的《命令与征服：将军》移植到了 iPhone 和 iPad 上，实现了原生 ARM64 编译和触屏操控。但社区分析 GitHub 提交记录后发现，约 2000 个提交中只有最后 19 个来自 Reshi，绝大多数来自开源项目 GeneralsX。 这一事件凸显了在移植工作中声称功劳与承认上游开源贡献之间的张力。同时，它也展示了将老款 RTS 游戏移植到 iOS 的技术复杂性，涉及 DXVK、MoltenVK 和自定义触控系统。 GeneralsX 项目始于 2025 年 2 月，在 EA 以 GPL v3 协议开源游戏代码后，已经完成了跨平台移植的大部分工作。Reshi 的贡献是最后的 iOS 特定适配，包括用于 Direct3D 到 Vulkan 转换的 DXVK、用于在 Metal 上运行 Vulkan 的 MoltenVK，以及触控系统。该移植无需模拟器，在 ARM64 上原生运行 2003 年的原始引擎。

twitter · dotey · 7月4日 22:58 · [原文链接](https://x.com/dotey/status/2073541964318883941)

**背景**: 《命令与征服：将军》是 EA Pacific 于 2003 年发行的即时战略游戏。2025 年，EA 以 GPL v3 协议发布了其源代码，使得 GeneralsX 等社区项目能够将其移植到现代平台。DXVK 将 Direct3D 调用转换为 Vulkan，而 MoltenVK 将 Vulkan 映射到 Apple 的 Metal API，两者结合使 Windows 游戏能在 iOS 上运行。Fable 5 是一个声称能简化此类移植的工具，但其在此处的具体作用存在争议。

**社区讨论**: 社区普遍批评 Reshi 夸大了自己的贡献，指出 GeneralsX 完成了核心工作。也有人承认 iOS 特定部分的难度，但认为功劳应更公平地分配。

**标签**: `#game development`, `#open source`, `#iOS port`, `#RTS`, `#Fable`

---

<a id="item-4"></a>
## [Baoyu-Design 技能现通过 Fable 5 支持 PPT 动画](https://x.com/dotey/status/2073286406558949828) ⭐️ 7.0/10

Baoyu-design 技能已更新，现支持 PPT 动画。此前，该技能生成基于 HTML 的 PPT，并借助 PptxGenJS 导出为 PPTX，但该库不支持动画。现在，通过利用 Fable 5 对 PPTX XML 格式的深入理解，该技能可以生成带有动画的 PPTX 文件。 此次更新显著提升了 baoyu-design 在制作演示文稿方面的实用性，因为动画是现代幻灯片的关键特性。它展示了像 Fable 5 这样的先进 AI 模型如何克服现有库的局限，使 AI 辅助设计工具能够输出更复杂的内容。用户现在可以直接通过 AI 提示生成带有动画的 PPT，节省时间并提高演示质量。 此次更新使用 Fable 5 直接操作 PPTX XML，绕过了 PptxGenJS 的动画限制。开发者指出，与原生 PPT 相比，动画细节上存在微小出入，但常用动画效果良好。该技能作为开源 Agent Skill 在 GitHub 上提供，用户可通过提供的链接试用。

twitter · dotey · 7月4日 06:02 · [原文链接](https://x.com/dotey/status/2073286406558949828)

**背景**: PptxGenJS 是一个流行的 JavaScript 库，用于以编程方式创建 PowerPoint 演示文稿，但不支持动画。Fable 5 是 Anthropic 的先进 AI 模型，擅长理解和生成 PPTX XML 等复杂文件格式。Baoyu-design 技能将 Claude Design 打包为可移植的 Agent Skill，允许本地 AI 代理生成包括演示文稿在内的视觉设计产物。

**标签**: `#AI tools`, `#presentation`, `#animation`, `#Fable`, `#open source`

---

<a id="item-5"></a>
## [AI 时代职业建议：领域专长胜于纯编程](https://x.com/dotey/status/2072904155572699375) ⭐️ 7.0/10

一条推文建议年轻人选择一个有热情的领域，并用 AI 来增强它，认为交付和领域知识比纯编程技能更重要。作者建议成为自己领域的“AI 带路党”，而不仅仅是程序员。 这一建议挑战了在 AI 时代学习编程是最安全职业路径的普遍观念。它强调了领域专长和实际应用的价值高于纯技术技能，这可能会影响职业选择和教育策略。 作者用海平面上升的比喻来描述 AI 对所有行业的必然渗透。他们强调“一个难看的小板凳”（交付的产品）比“挂在嘴上的躺椅”（空谈）更实在。原推文@xicilion 认为未来十年 AI 将掠夺所有行业，需要程序员作为炮灰。

twitter · dotey · 7月3日 04:43 · [原文链接](https://x.com/dotey/status/2072904155572699375)

**背景**: 这场讨论是有关 AI 对工作和技能影响的更广泛辩论的一部分。许多人认为编程是安全的选择，但这一观点认为领域专长结合 AI 工具将更有价值。“AI 带路党”的概念指的是将 AI 应用于特定领域的人，而不是构建 AI 本身。

**社区讨论**: 未提供社区讨论内容，但推文引用了@xicilion 的观点，即程序员将成为 AI 掠夺中的炮灰，而作者则通过倡导领域专长来反驳。

**标签**: `#AI`, `#career advice`, `#software engineering`, `#education`, `#industry trends`

---

<a id="item-6"></a>
## [GLM-5.2 现可通过 Hugging Face 在 Claude Code 中使用](https://x.com/Zai_org/status/2073449055334838362) ⭐️ 7.0/10

Z.ai 的 GLM-5.2 模型现在可通过 Hugging Face Inference Providers 和 hf-claude 集成在 Claude Code 中选择使用。这使得开发者可以直接在 Anthropic 的 AI 辅助编码环境中使用该开放模型。 这一集成简化了希望在流行编码助手中利用 GLM-5.2 等开放模型的开发者的工作流程。它标志着开源模型与商业 AI 工具之间互操作性向前迈出一步，可能加速开放模型在实际开发中的采用。 GLM-5.2 是一个 744B 参数模型，具有 40B 活跃参数和 1M token 上下文窗口，针对编码和推理等长周期任务进行了优化。该集成使用 Hugging Face Inference Providers（将多个推理合作伙伴统一到单个 OpenAI 兼容 API 下）和 hf-claude 工具，将 Hugging Face 模型与 Claude Code 连接起来。

twitter · Zai_org · 7月4日 16:49 · [原文链接](https://x.com/Zai_org/status/2073449055334838362)

**背景**: Claude Code 是 Anthropic 的 AI 驱动编码助手，帮助开发者编写、调试和重构代码。Hugging Face Inference Providers 提供统一 API，无需管理基础设施即可访问多个提供商的模型。GLM-5.2 是 Z.ai 最新的开源模型，是 GLM-5.1 的继任者，在长上下文和智能体能力方面有显著改进。

**标签**: `#AI`, `#open-source`, `#developer-tools`, `#GLM-5.2`, `#Claude Code`

---

<a id="item-7"></a>
## [Karpathy 分享 Fable 的 60 多个 3D 提示演示](https://x.com/karpathy/status/2073496962566164990) ⭐️ 6.0/10

Andrej Karpathy 转发了 Peter Gostev 的帖子，该帖子展示了一段 45 分钟的视频合集，包含来自 Fable 的 60 多个 3D 提示演示。视频展示了具有挑战性的 3D 提示，并在后续帖子中提供了提示内容。 这个合集为 AI 驱动的 3D 内容创作提供了实用示例，这是一个快速发展的领域。它帮助从业者了解当前 3D 提示工具的能力和局限性，可能加速在游戏开发和设计中的采用。 该视频时长 45 分钟，包含 60 多个演示，专注于 Fable 中最难的 3D 提示。提示内容在后续帖子中分享，允许其他人复现结果。推文未明确说明使用的是哪个 Fable 平台或工具，但很可能指的是一个 3D 生成服务。

twitter · karpathy · 7月4日 19:59 · [原文链接](https://x.com/karpathy/status/2073496962566164990)

**背景**: 3D 提示是指通过 AI 使用自然语言或图像生成 3D 模型，类似于文本到图像生成。Spline AI、Meshy 和 3D AI Studio 等工具允许用户通过提示创建 3D 资产，无需手动建模。Fable 似乎是一个专注于 3D AI 生成的平台或公司，但搜索结果中缺乏详细信息。

**标签**: `#3D prompting`, `#AI demos`, `#content creation`, `#Fable`

---