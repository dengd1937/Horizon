---
title: 控制 LLM 的推理投入
source_url: https://magazine.sebastianraschka.com/p/controlling-reasoning-effort-in-llms
source_domain: magazine.sebastianraschka.com
published_date: '2025-07-19'
added_date: '2026-07-18'
slug: magazine-sebastianraschka-com-20250719-llm-reasoning-effort
summary: 本文系统梳理 LLM 推理投入设置的训练与推断机制，比较六个开放权重模型的模式控制、预算与强化学习方案。
tags:
- 推理模型
- 工程实践
cover: https://substack-post-media.s3.amazonaws.com/public/images/286a0beb-32b2-41fc-8bcf-6bae189b53f2_1488x840.png
---

# 控制 LLM 的推理投入

### LLM 如何学习低、中、高投入的推理模式

OpenAI 发布 o1、并由其普及基于 LLM 的推理模型概念，至今已近两年。约四个月后，DeepSeek-R1 随之发布，并披露了用可验证奖励强化学习（RLVR）训练此类推理模型的方法。

上周，OpenAI 发布 GPT-5.6 模型家族。它有三个尺寸，每个尺寸大约提供五到六档推理投入设置。

![](https://substack-post-media.s3.amazonaws.com/public/images/d495118a-85cb-49e5-b71c-8f7e6e07fa12_1999x1237.png)

图 1：GPT 5.6 Sol 模型的不同推理投入设置。（Ultra 的基准数值目前尚不可用；但它使用与 Max 相近的投入级别，只是以四个子智能体加速工作，因此结果应相对类似。）

所以，推理模型会长期存在，已成为现代模型发布的标准组成部分。

过去我介绍过推理模型的方法论（[理解推理 LLM](https://www.google.com/url?q=https://magazine.sebastianraschka.com/p/understanding-reasoning-llms&sa=D&source=editors&ust=1784335866721316&usg=AOvVaw3KNY841B7H7EqshVnEJp8D)）及相关论文（[LLM 推理强化学习现状](https://www.google.com/url?q=https://magazine.sebastianraschka.com/p/the-state-of-llm-reasoning-model-training&sa=D&source=editors&ust=1784335866721667&usg=AOvVaw1WaEOS_3zXEmP9JnLDSoZK)和[LLM 推理模型推断现状](https://www.google.com/url?q=https://magazine.sebastianraschka.com/p/state-of-llm-reasoning-and-inference-scaling&sa=D&source=editors&ust=1784335866721813&usg=AOvVaw2nWsugtg_XcMLKTUGcnk7B)）。我还写了一本讲解如何开发推理模型的 440 页新书：[从零构建推理模型](https://www.google.com/url?q=https://sebastianraschka.com/books/%23build-a-reasoning-model-from-scratch&sa=D&source=editors&ust=1784335866721991&usg=AOvVaw1JZMrDei_qWFsW_OMMNnyL)。

![](https://substack-post-media.s3.amazonaws.com/public/images/32631933-be29-4539-92ff-724c938342af_1965x1999.png)

图 2：我的新书《从零构建推理模型》，彩色版！

这些资源聚焦于将传统 LLM 变成推理模型。本文则聚焦解释：如何开发拥有多种投入模式的推理模型，类似本文开头图中的模型。

不必担心，本文可独立阅读；不过上述资源也许会有趣且有用。

## 1\. 推理模型的简要定义

谈论几乎任何机器学习或 AI 技术、子领域时，都不应按字面理解技术术语。例如，机器学习和 AI 中的（人工）神经网络并不真的像人脑这样的生物神经网络工作。

同样，谈论“推理模型”时，也不应期待它们真的像人类一样推理。在 AI 与 LLM 研究中，“推理模型”指会输出中间推理轨迹的模型；它像一段中间回答，会逐步处理问题或任务。

最容易的解释方式或许是展示一个例子。

![](https://substack-post-media.s3.amazonaws.com/public/images/cfe5f6a8-8b9e-422f-a8fb-4c3427129d61_1999x1162.png)

图 3：传统 LLM 回答（左）与推理模型回答（右）的示意。

## 2\. 推理模型的训练扩展与推断扩展概览

本质上，提升（推理）任务表现有两条路径：训练扩展与推断扩展。

![](https://substack-post-media.s3.amazonaws.com/public/images/4efb291d-6cd3-4fba-ab3a-bac088cb2601_1999x961.png)

图 4：训练扩展和推断扩展是提升 LLM 与推理模型解题能力的两种方式。图基于《用 LLM 学会推理》。

先简要讨论训练。

## 2.1 训练推理模型

简言之，[DeepSeek-R1](https://arxiv.org/abs/2501.12948) 提出用可验证奖励强化学习（RLVR）训练 LLM，使其成为推理模型。RLVR 会对可验证数据领域提供奖励信号（`0=错误`、`1=正确`）。这里的可验证领域是数学（可用 SymPy 或 WolframAlpha 等符号数学检查器核验结果）和代码（可用编译器、单元测试或 LeetCode 等集成平台检查正确性）。

![](https://substack-post-media.s3.amazonaws.com/public/images/874e07b2-d461-4ae5-bbda-f8204ae16420_1999x945.png)

图 5：RLVR 训练中准确率奖励与格式奖励的示意。

值得注意的是，推理轨迹本身未用于训练或更新模型。虽然作者尝试把这些中间回答信息用于训练，DeepSeek-R1 论文称它对模型训练无帮助，最终没有采用。（如何通过过程奖励模型将中间推理轨迹纳入训练信号，仍是活跃研究方向。）

![](https://substack-post-media.s3.amazonaws.com/public/images/a8ffc0b7-2ba0-462e-98a6-734226250175_1999x925.png)

图 6：RLVR 忽略中间推理轨迹；只有最终答案和回答格式决定奖励。

## 2.2 “啊哈”时刻

无论如何，仅以输出奖励训练，如图 7 所示，已足以让模型学会推理问题：学会写出中间解释、回溯及自我纠正。模型意识到犯错并自我修正的时刻，被称为“啊哈”时刻。

![](https://substack-post-media.s3.amazonaws.com/public/images/e934cf9d-40a0-4907-9505-275bbbbb4864_1999x1413.png)

图 7：一个“啊哈”时刻示例：推理模型察觉中间推理错误，并在给出最终答案前修正它。

顺带一提，DeepSeek-R1 无疑是更流行、也引发 RLVR 与推理模型开发热潮的论文；但另有一篇 [Kimi K1.5](https://arxiv.org/abs/2501.12599) 在同一天（2025 年 1 月 22 日）发布到 arXiv。RLVR 一词还早两个月就已在 [Tülu 3：推进开放语言模型后训练的前沿](https://arxiv.org/abs/2411.15124)中提出。

DeepSeek R1 最终更受欢迎的一个原因，是它证明仅用纯强化学习（RL）即可获得推理行为。

![](https://substack-post-media.s3.amazonaws.com/public/images/8f1de0d2-97b8-4222-9cb6-b33e5bb5ad4e_1999x772.png)

图 8：DeepSeek-R1-Zero 直接将 RLVR 应用于预训练基础模型，无需监督微调。

例如，Tülu 3 和 Kimi K1.5 都在监督微调（SFT）模型之上再应用强化学习。DeepSeek-R1 也从 DeepSeek-V3 基础模型的 SFT 检查点训练，并包含一个以纯 RLVR 训练的 DeepSeek-R1-Zero 变体。R1 Zero 弱于 R1，但证明 RLVR 足以教会模型生成和使用推理轨迹。

R1-Zero 更像概念验证模型；如上所述，完整 DeepSeek-R1 推理模型的训练管线通常是多阶段且更复杂的。

![](https://substack-post-media.s3.amazonaws.com/public/images/918b28a0-01aa-45b0-91ec-21f2624276d6_1999x1508.png)

图 9：更详细的推理模型训练管线。此图描绘各种 DeepSeek-R1 模型。更多细节见我的另一篇文章《理解推理 LLM》。

顺带一提，今日多数 LLM 实际上都是推理模型，即它们已通过与 DeepSeek-R1 类似、某种形式的 RLVR 训练。

## 2.3 推断扩展概要

除通过训练改善推理行为外，另一个提升模型表现的杠杆是推断计算扩展。简言之，即在模型训练完成后、使用期间投入更多计算，以获取更好的答案。

这本身是一个完整主题；如需细致梳理，可阅读我的《LLM 推理模型推断现状》：

下面我会概括最需要作为背景说明的部分。

第一，用 RLVR 训练模型本身已隐式带来一种推断扩展，因为推理模型在推断时通常比传统 LLM 输出更多 token，这意味着推断期间花费更多计算。

第二，我们还能通过推理投入级别进一步调节输出长度，稍后会详细说明。

第三，还有许多额外的推断扩展技术。流行方法之一是自一致性，常实现为多数投票：多次查询模型，再通过多数票选取最终答案。

![](https://substack-post-media.s3.amazonaws.com/public/images/5ce7222d-19fb-4578-a9ec-aa60f21d5587_1999x1185.png)

图 10：自一致性这一流行推断扩展技术的示例。

它可用于传统 LLM 或推理模型，也可按需使用，并与推理训练叠加。一个好例子是 DeepSeekMath-V2：研究人员在专长数学的推理模型上实施极端推断扩展，在困难的数学奥赛类问题上获得最先进表现。

![](https://substack-post-media.s3.amazonaws.com/public/images/8103d00f-ddd8-457d-b115-545311d7c40e_1999x1338.png)

图 11：将两种推断扩展（自一致性与自我细化）结合以提升数学表现。图改编自《DeepSeekMath-V2：迈向可自验证的数学推理》。

但同样，其他技术概览请参阅我的《LLM 推理模型推断现状》：

## 3\. 思考 token

你可能已在前面“啊哈”时刻图中见过 `<think></think>` token。为免你滚回上方，我也在下方放入相应图。

![](https://substack-post-media.s3.amazonaws.com/public/images/ec1eeb79-6e2d-4236-a9e4-fdd6b61517e5_1999x1236.png)

图 12：推理模型中常见的格式 token。

这些 `<think>` 和 `</think>` 标签对推理能力而言只是外观标记。它们不会使模型推理，也不是获得好推理表现的必要条件。用其他分隔符训练同一模型，很可能也能达到相似基准表现。

这些 `<think>` 标签或 token 的主要目的，是标记推理轨迹起止位置，让训练管线或用户界面能将其与最终答案分开，并可选地对用户隐藏。（ChatGPT 或 Codex 等 UI 通常如此。）

关键在于，`<think>` token 并未赋予模型“思考”、推理或更好推理的能力。不使用这类 `<think>` token 训练同一模型，也可达到类似基准表现。

字面字符串 `<think>` 与 `</think>` 也没有特殊之处；另一对分隔符也能实现同一目的。

顺带一提，典型实现是在 RLVR 阶段加入格式奖励。因此，不只是按答案正确性奖励模型，也会额外奖励使用 <think> token，从而鼓励模型使用它们。

例如，在 DeepSeek-R1 中，总奖励计算为：

`R_total = R_accuracy + R_format`

其中格式奖励是简单的规则检查，鼓励模型把推理放在：

`<think>`

推理轨迹

`</think>` 中。

## 4\. 推理模式的开关

第一代推理模型是专用推理模型：有 DeepSeek-V3 基础模型，也有独立的 DeepSeek-R1 推理模型。

无论提示词是什么，R1 通常都会用大量 token 输出很冗长的回答，即使是简单提示也一样。它还缺乏关闭推理模式的内置选项。

![](https://substack-post-media.s3.amazonaws.com/public/images/2f980538-0730-4518-a685-d1574cd78b7a_1999x1271.png)

图 13：推理模型即便面对最简单的提示词也非常冗长。

后来的模型（如 Qwen3 等）试验混合方法：同一个模型可按需表现为常规指令微调模型或推理模型。

> 注：一些模型开发者称之为“思考模式”，另一些称为“推理模式”；二者指同一行为。

在 Qwen3 中，这通过 tokenizer 的 `enable_thinking=True` 或 `enable_thinking=False` 实现。底层上，设置 `enable_thinking=False` 本质是在助手回答开头加入空的 `<think></think>` 段落，从而关闭 Qwen3 的推理（“思考”）模式。

![](https://substack-post-media.s3.amazonaws.com/public/images/bbaa28da-a17e-462b-88d3-4c28ac863ef6_1999x1224.png)

图 14：Qwen3 0.6B 推理模型在 thinking=False 与 thinking=True 下的回答。（左侧界面隐藏空标签，因为它们属于修改后的输入提示词，而非生成的答案。）

训练时如何实现，才能让模型在推断时支持如上图所示的开关？

简言之，正如[Qwen3 技术报告](https://arxiv.org/abs/2505.09388)所述，这种开关行为主要经由监督微调（SFT）引入，随后在其最大的旗舰模型中由通用 RL 强化。

例如，在通过长链思维 SFT 与推理 RL 训练初始推理模型后，作者加入“思考模式融合”阶段。在这一额外 SFT 阶段，模型同时看到思考与非思考示例：

- `/think: <think>{reasoning}</think>{answer}`
- `/no_think: <think></think>{answer}`

思考是默认行为，因此也可省略 /think。随后的通用 RL 阶段会进一步强化此模式和格式遵循。

这些 `/think` 与 `/no_think` 标志是“软”开关。不过，前述 `enable_thinking=False` 设置会在 False 时强制加入空的 `<think></think>`，因此属于“硬”开关。

![](https://substack-post-media.s3.amazonaws.com/public/images/d170e1f6-0838-487e-b3a6-7d501eb38962_1999x914.png)

图 15：Qwen3 训练管线中的“思考模式融合”，用于实现推理模式开关。

换言之，tokenizer 不会在查询中添加 `/no_think`，而是在助手回答开头直接填入空 `<think></think>` 段落。模型只看到所得 token，并直接继续生成答案。

无论如何，这一开关本质上是 GPT-5.6 等模型推理投入级别的简化版本，下一节会介绍。

## 5\. “推理投入”设置如何工作

本节将简要概述不同推理投入开关可能的实现方式；这类设置由 GPT 5 等模型引入，如今几乎所有旗舰模型都有。

具体来说，本文开头展示过 Codex GPT 5.6 界面的图，用户可在其中选择多个推理“投入”设置。

![](https://substack-post-media.s3.amazonaws.com/public/images/1b0330fd-e315-4207-b0eb-2dc4aa358619_1999x1035.png)

图 16：GPT-5.6 提供六档推理投入设置，从 Light 到 Ultra。

下一小节将说明这些设置可能怎样实现；之后一节会讨论一些与此主题相关、更有意思的研究论文。

## 5.1 推理投入、回答长度与质量

遗憾的是，OpenAI 没有公开投入设置的实现细节，但仍有一些可用于合理推测的证据。

例如，通过去年的开源 gpt-oss 模型（我在[《从 GPT-2 到 gpt-oss：分析架构演进》](https://magazine.sebastianraschka.com/p/from-gpt-2-to-gpt-oss-analyzing-the)中讨论过），我们知道 OpenAI 允许通过附加到每个提示词前的系统提示词（“Reasoning effort: low/medium/high”）切换推理投入设置。

![](https://substack-post-media.s3.amazonaws.com/public/images/e3224bad-f1e2-4707-8839-3076527e594e_1999x690.png)

图 17：gpt-oss 聊天模板会在向同一模型发送提示词前，将所选推理投入插入系统消息。

正如预期，推理投入会直接影响回答长度和准确率，如下图所示。

![](https://substack-post-media.s3.amazonaws.com/public/images/955e50d8-530d-46ad-b61a-eee878028992_1999x818.png)

图 18：gpt-oss 模型在不同推理投入下的回答长度与质量（模型卡中的标注图）。

推测其 GPT 5 模型（包括最新 GPT 5.6）采用类似方法。

顺带注意上图中不同投入设置如何扩展回答长度。投入级别似乎与 token 用量直接相关，token 用量又似乎与准确率相关。也许能构想高于“high”的投入设置，但表现应会在某处饱和。GPT 5.6 Sol 模型更清楚显示这种饱和：增大推理预算会在某个点变得不经济。

![](https://substack-post-media.s3.amazonaws.com/public/images/cbee0ac2-1321-4d44-bda1-a0b5fc078f19_1999x1223.png)

图 19：推理投入同时提高 API 成本与编码智能体表现；最高 GPT-5.6 设置的回报递减。图基于 Artificial Analysis Coding Agent Index v1.1。

另一个展示推理投入、token 用量和基准表现关系的近期数据点，是 Thinking Machine Labs 本周发布的新[开放权重 Inkling](https://sebastianraschka.com/blog/2026/inkling-architecture-benchmark-notes.html)。

![](https://substack-post-media.s3.amazonaws.com/public/images/3dfb81aa-5ae7-4038-b8e5-f0b7a950f15e_1999x1032.png)

图 20：提升 Inkling 投入级别通常会增加生成 token 和基准表现，但高投入时增益递减或不均匀。图来自 Inkling 公告博文。

如本节讨论，推断期间可简单用系统提示词控制推理投入级别。（ChatGPT UI 推测只是将菜单选择映射为系统提示词。）但这对任意模型并不适用，需要对训练管线进行特定修改，下一节将讨论。

## 5.2 推理投入级别的可能实现

虽然 GPT 5.6 和开源 gpt-oss 模型都未公开训练细节，通常会在后训练期间将推理投入标签包含在提示词中。

典型有两种实现方式。

第一种是在 RLVR 流程中实现：当使用不同系统提示词时施加不同长度惩罚。例如，“Reasoning effort: low”采用高长度惩罚，“Reasoning effort: high”采用轻微或无惩罚。

第二种是在 RLVR 后用监督微调（SFT）训练模型遵循不同投入指令。

例如，在核心 RLVR 阶段之后、SFT 期间，训练数据集中的提示词会与呈现所需推理量的目标回答配对。（目标可以由人写、由另一个模型生成，或先生成再筛选。）

![](https://substack-post-media.s3.amazonaws.com/public/images/f059bb1a-d06d-4a8b-81b3-5c78c5fa0551_1999x1169.png)

图 21：以投入为条件的 RLVR 与 SFT 示意。（这是可能实现，而非对 OpenAI 训练管线的确认描述。）

在此 SFT 阶段，模型直接从训练示例学习投入标签与目标推理长度的关联。基于 RL 的实现则会在 RLVR 阶段内放置投入标签与预算感知奖励。两种做法也可结合；我怀疑 gpt-oss 与 GPT 5.6 都这样做了（注意，GPT 5.6 的投入设置可能只是改变某个用户查询的系统提示词）。

## 5.3 Inkling 案例研究

刚发布的 Inkling 技术报告给出了一个小而相对具体的投入级别训练示例。

![](https://substack-post-media.s3.amazonaws.com/public/images/d6a88041-747e-494a-aacd-d4c6f7925b94_1999x987.png)

图 22：Inkling 扫描 0.2 至 0.99 的连续投入值；更高投入通常带来更长回答和更高基准分数。

在大规模 RL 中，他们对每个样本做两件事：

1. 在系统消息中指定期望的投入级别。
2. 调整为每个生成 token 赋予的成本。

概念上，奖励可能类似：

$R \left(\right. e \left.\right) = R_{\text{task}} - \lambda \left(\right. e \left.\right) N_{\text{tokens}}$

这里，*e* 是请求的投入级别，λ(e) 控制 token 惩罚。

- 低投入采用更大的每 token 成本，鼓励较短推理轨迹。
- 高投入采用更小的每 token 成本，允许模型花费更多 token。

随后在推断时，Inkling 接收如 Thinking effort level: 0.8 的系统消息，并据此调整 token 用量。Inkling 与 gpt-oss、GPT-5.6 等模型的区别在于：其投入标签是 0 至 1 的连续数值，而非 low、medium、high 等有序标签。

这说明 Inkling 的投入条件化主要位于 Reasoning RL 阶段，而不只在后续 SFT 阶段。

不过，他们未披露确切奖励公式、token 成本系数，或是否也在 SFT 中加入投入条件化。

## 5.4 关于推断扩展与训练扩展的简短说明

进入推理投入论文前，我想把本节与先前“2.3 推断扩展概要”连接起来。

前面我把扩展分为训练计算扩展与推断时扩展。GPT-5.6 界面很好地展示了二者差异，如下图。

左侧选择 Luna、Terra 或 Sol 会改变模型本身。粗略类比，这对应训练计算扩展：它们是分别训练的模型。在固定训练配方和数据集规模下，更大模型需要更多训练计算，且每个生成 token 通常也需要更多计算。

右侧保持模型不变，只改变推理投入。这是推断时扩展：模型权重相同，但模型被允许为回答花费更少或更多 token。

![](https://substack-post-media.s3.amazonaws.com/public/images/fe3daa10-2327-4fa4-a71e-c318298e8b85_1999x1395.png)

图 23：模型选择与推理投入菜单对应两条不同扩展轴。选择 Luna、Terra 或 Sol 会改变模型；改变推理投入则调整固定模型的推断时计算。

有一条术语注意：此刻从菜单选择不同模型并不是训练扩展，训练已发生。更好理解是：模型菜单在选择由不同训练规模产生的模型。

下方 Artificial Analysis 结果展示这两条轴在实践中如何交互。

每条蓝色曲线对应 Luna、Terra 或 Sol 中的一个模型。沿曲线提高推理投入，是推断扩展；从一条模型曲线移至另一条，则对应模型扩展，我在这里将其作为训练扩展的实用代理。

正如预期，两种方法都可提升基准分数，但也增加成本。更有趣的是曲线会重叠：较小模型在较高推理投入下，有时可达到与较大模型在较低投入下相近的分数。

![](https://substack-post-media.s3.amazonaws.com/public/images/5556b75b-3029-4134-8fad-3a243d7e36d7_1999x1514.png)

图 24：Artificial Analysis Coding Agent Index 上 GPT-5.6 模型家族的训练扩展与推断扩展。沿每条模型曲线移动对应提高推理投入；跨 Luna、Terra、Sol 曲线移动对应选择不同模型。

顺带一提，本图 x 轴展示 API 成本而非原始计算。API 成本是实用指标，但也取决于提供商定价和生成 token 数；曲线的确切形状也依赖具体基准。

因此，模型尺寸与推理投入是两个独立旋钮。可使用更大模型、提高推理投入，或二者结合；最佳组合取决于所需准确率、成本和延迟。

到此，本文已应能让你扎实理解推理投入模式及其实现。若时间有限，这里适合结束；否则如想了解近期开放权重模型的一些细节，请继续阅读。

## 6\. 附加：旗舰开放权重 LLM 实现推理投入的不同方式

**\[除非你想了解额外细节，否则本节可跳过\]**

第 5 节描述了训练推理投入控制的两种可能方式：以投入为条件的监督微调，以及采用不同 token 成本的强化学习。起初我想覆盖替代性推理预算实现的研究论文，但读过多数文章后，感觉它们更像未必能在实践中良好工作的概念验证。

因此，我转而介绍最先进、值得注意的开放权重（旗舰）LLM 所使用的配方。对这些模型，至少有证据表明方法可在实践中奏效。

这里留下六个例子：DeepSeek V4、Nemotron 3 Ultra、Kimi K2.5、GLM-5、Qwen3 和 Inkling。它们报告细节不同，但每个都提供有用变体。（我排除了只在 UI 展示投入设置、却不解释该行为如何训练的模型。）

## 6.1 DeepSeek V4 训练独立的投入专家

先看 [DeepSeek V4 技术报告](https://www.google.com/url?q=https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/resolve/main/DeepSeek_V4.pdf?download%3Dtrue&sa=D&source=editors&ust=1784335866750314&usg=AOvVaw2n1GwYNTZHYZE3wfXDbrZJ)，其中描述三种模式：

- **Non-think** 直接给出回答，不产生推理轨迹。
- **Think High** 是经典方法：模型把推理轨迹放在 <think> 与 </think> 标签间，类似本文开头第 2 节所述 DeepSeek R1。
- **Think Max** 与上述相同，但会增加特殊系统指令。（稍后说明。）

Think Max 的额外系统提示词以“Reasoning Effort: Absolute maximum with no shortcuts permitted.”开头。

![](https://substack-post-media.s3.amazonaws.com/public/images/fcbdaaec-9833-49c4-ba95-be65d7626b3c_1999x1506.png)

图 25：DeepSeek V4 文档中的推理投入控制概览。

初看这像简单提示词工程技巧，但该提示词其实由不同训练设置支撑：每种模式都有自己的上下文窗口和长度惩罚（报告未详述确切惩罚实现）。Think Max 获得比 Think High 更长的上下文窗口和更小的长度惩罚，因而有更多空间继续推理。

因此，系统指令选择的是后训练创造的行为；将相同指令加到任意模型上不会产生相同效果。

![](https://substack-post-media.s3.amazonaws.com/public/images/abdfb97b-7fa7-4a99-9d8d-0d62f038ceaf_1999x1161.png)

图 26：DeepSeek V4 在报告不同部分分别描述三种投入模式和更大的教师池。教师池包含十多个领域专家；报告未披露这些教师如何映射至 Non-think、Think High、Think Max。

遗憾的是，这份公开且很详细的 DeepSeek V4 报告未将推理模式与领域专家的描述充分连接，无法重构准确教师分配。

但报告称，支持不同推理投入级别的最终模型，是通过从这些教师进行 on-policy 蒸馏创建的。

总结来说，DeepSeek V4 在后训练中开发三种推理专家。从基础模型出发，应用监督微调，再通过 GRPO 进行 RLVR。每种模式的 RL 配置不同；特别是每位专家都有自己的上下文窗口和长度惩罚，而 Think Max 还得到特殊系统指令。

之后，连同领域专家在内，各种推理模式专家被蒸馏进一个支持全部三种投入模式的单一检查点。

## 6.2 Nemotron 3 Ultra 将学习到的模式与硬预算结合

[Nemotron 3 Ultra 技术报告](https://www.google.com/url?q=https://research.nvidia.com/labs/nemotron/files/NVIDIA-Nemotron-3-Ultra-Technical-Report.pdf&sa=D&source=editors&ust=1784335866753580&usg=AOvVaw2ekgj61BJagCXY9Lb5Ho9k)描述 reasoning-off、regular 和 medium-effort 三档设置，与上一节 DeepSeek V4 类似。相较 regular，medium-effort 是更便宜的推理模式。NVIDIA 在 SFT 中使用 GPT-OSS-120B 的 medium-effort 模式生成示例引入该模式，随后在 RLVR 中继续优化。约 2.5% 的 RLVR 提示词使用 medium-effort（对应对奖励应用的长度调整）。

### 6.2.1 在推断中使用 Nemotron 推理预算

推断时，三种模式均通过[聊天模板](https://www.google.com/url?q=https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4/blob/main/chat_template.jinja&sa=D&source=editors&ust=1784335866754576&usg=AOvVaw0MHEpfuuYzvMuv4pqOfPsL)选择。

![](https://substack-post-media.s3.amazonaws.com/public/images/3da56169-dec2-4804-b552-b2f42cd79d28_1362x1999.png)

图 27：经由聊天模板的 Nemotron 3 Ultra 推理设置（官方模型卡示例）。

1) Regular 是默认模式，使用 `enable_thinking=True`，令助手回答以 `<think>` 开标签开始。

2) Medium-effort 使用 `enable_thinking=True` 与 `medium_effort=True`，后者还会在最新用户消息后附加 {reasoning effort: efficient}。

顺带一提，regular 和 medium-effort 模式也可与单独的推断时推理预算结合。该预算充当外部停止机制。发布的实现中，聊天客户端要求模型在所选 token 上限附近结束推理轨迹；若模型还未输出 `</think>`，客户端关闭推理块并继续生成最终答案。学习到的投入模式决定模型如何使用推理 token，预算则限制推理轨迹可持续多久。因此，可按所需成本和准确率，为任一模式配更紧或更松的预算。

3) Reasoning-off 使用 `enable_thinking=False`，预填空 `<think></think>` 块（类似第 4 节的 Qwen3），使模型直接进入最终回答。因此这些是聊天模板控制，而非系统提示词。

### 6.2.2 Nemotron 中的推理预算感知训练

上述推断控制由两个相关 SFT 组件支撑。第一个如前所述，以 GPT-OSS-120B 轨迹引入 medium-effort 行为；第二个让模型适应硬推理预算。

构造训练数据时，作者取 regular 推理轨迹，在随机选择的 token 预算处截断，保留原最终答案；插入的 `</think>` token 会从 SFT 损失中掩蔽。因此模型看到的示例是：推理轨迹不完整、推理块被外部关闭后仍须转向答案。

Medium-effort 训练随后在 RLVR 中继续。约 2.5% 的 RL 提示词在数学、STEM 和编码任务中使用 medium-effort 设置。报告指出可通过奖励超参数校准模式，基于长度的奖励调整可额外控制成本—质量权衡。

![](https://substack-post-media.s3.amazonaws.com/public/images/efb9a0f0-fbbf-4bfb-b45a-36eebdb39200_1999x1264.png)

图 28：Nemotron 3 Ultra 通过教师生成的 SFT 数据、随机预算截断和 RLVR 中小比例的 medium-effort 子集引入中等投入。

## 6.3 Kimi K2.5 交替进行有预算与无约束 RL

[Kimi K2.5 技术报告](https://www.google.com/url?q=https://arxiv.org/abs/2602.02276&sa=D&source=editors&ust=1784335866757827&usg=AOvVaw1ZQ2g58qlTcuh8v5EJoJo6)讨论一种用于较低推理投入、名为 Token Efficient RL 的训练方法。（本周虽有 K3 公告，但未公开 K3 的推理投入方法，可能与 K2.5 类似或相关。）

### 6.3.1 Kimi 的 Toggle 方法

报告指出，固定 token 预算会让推理模型过拟合短解：模型更简洁、更快、更便宜，却可能失去从额外推断时计算中获益的能力，导致表现变差。

![](https://substack-post-media.s3.amazonaws.com/public/images/567e7d9a-e564-480e-8981-0359c032220e_1999x1286.png)

图 29：所提 Toggle 方法让 Kimi K2.5 更具 token 效率，同时总体基准表现相近。图标注自 https://arxiv.org/abs/2602.02276。

Kimi K2.5 的 Toggle 方法每隔固定训练迭代数，在两个 RL 阶段间交替：

1\. 有预算阶段鼓励正确解保持在问题特定的 token 预算内。

2\. 无约束阶段恢复通常最大生成长度，让模型仍能从较长解中学习。

每题预算根据 RLVR 中正确 rollout 回答长度的选定分位数估计；仅当该题平均准确率超过阈值时才激活预算约束，从而避免模型尚未可靠解题前就被迫缩短推理。

![](https://substack-post-media.s3.amazonaws.com/public/images/1b1ecf39-b55e-44fb-a756-8b6a8875ba87_1999x714.png)

图 30：Toggle 方法两个阶段概览。

报告在 K2 Thinking 上评估 Toggle，发现生成 token 减少约 25% 至 30%，基准表现变化很小；该行为还可从数学、编码 RL 任务迁移到 GPQA 和 MMLU-Pro。

Toggle 为训练更具 token 效率、又保留测试时扩展能力的推理策略提供了具体旗舰模型配方。

### 6.3.2 Toggle 在推断时改变什么

Toggle 完全在 RL 训练中运行。两个交替阶段更新同一策略（即 LLM），最终统一检查点没有有预算/无约束选择器；推断时模型默认以思考模式运行。

不过，我查看的一些 API（如 vLLM、SGLang）中，Kimi K2.5 自身暴露了 thinking 与 instant 的单独二元选择。thinking 默认开启；instant 通过官方 API 的 thinking: `{”type”: “disabled”}` 或 vLLM/SGLang 服务时的 `chat_template_kwargs={”thinking”: False} ` 禁用推理轨迹。但这些设置与 Toggle 无关。

官方 Kimi 报告也未给出 instant 模式的单独训练配方。不过 K2.5 的 SFT 数据同时由较早的直接回答 K2 与产生长推理轨迹的 K2 Thinking 生成，这可能使统一检查点接触两种回答格式，类似 Nemotron 3。推断时聊天模板以开放 `<think>` 标签选择思考模式，或以空 `<think></think>` 块选择 instant 模式；但报告未披露确切数据混合或是否使用额外的模式专属 RL。

较新的 Kimi K3 提供更直接的推断时投入接口。[当前 Kimi Code 文档](https://www.google.com/url?q=https://www.kimi.com/code/docs/en/kimi-code/models.html&sa=D&source=editors&ust=1784335866762281&usg=AOvVaw0CXvoqLeEwnu6kmnN71eNY)列出 low、high、max 三档，默认 max，并通过 `reasoning_effort` 参数传入。不过 Moonshot 尚未说明三档如何在训练中产生；其[发布文章](https://www.google.com/url?q=https://www.kimi.com/blog/kimi-k3&sa=D&source=editors&ust=1784335866762950&usg=AOvVaw1kAEhIZfnu-LTk8yd5xgal)称细节将在未来 K3 技术报告公布，值得关注。

## 6.4 GLM-5 通过 SFT 引入回合级与交错思考

[GLM-5 技术报告](https://www.google.com/url?q=https://arxiv.org/abs/2602.15763&sa=D&source=editors&ust=1784335866763311&usg=AOvVaw2B0_xQjtDj2xC_zTXgUmxa)将 GLM-4.5 引入的二元思考开关扩展到多回合、工具使用情形，描述三种相关行为（而非三档投入）：

- **交错思考：**在每次回答和工具调用前插入推理块。
- **保留思考：**聊天跨回合保留先前推理块，以便模型稍后复用。
- **回合级思考：**在对话中为每一请求分别开启或关闭推理。

推断时，回合级思考是真正开关。在 [Z.ai API](https://www.google.com/url?q=https://docs.z.ai/guides/capabilities/thinking-mode&sa=D&source=editors&ust=1784335866764242&usg=AOvVaw1l0q9ZQ6McPYsOnvRmKeNL)中，思考默认开启，可针对单请求用 thinking: `{”type”: “disabled”}` 关闭。托管实现未披露，但开放的 [GLM-5 聊天模板](https://www.google.com/url?q=https://huggingface.co/zai-org/GLM-5/blob/main/chat_template.jinja&sa=D&source=editors&ust=1784335866764572&usg=AOvVaw3Be1R4iJTIh-fDCVr1CbF6)展示了用 Transformers、vLLM 或 SGLang 自托管时的等价机制。

思考开启时，助手回答以 `<|assistant|><think>` 开始；关闭时以 `<|assistant|></think>` 开始，后者立即关闭推理块，因此生成直接进入最终答案。

报告称，这些行为在多任务 SFT 中与更新后的聊天模板一起引入。

SFT 后，GLM-5 依次经过推理 RL、智能体 RL 与通用 RL；最终 on-policy 蒸馏使用此前阶段检查点作为教师，帮助最终模型恢复在顺序 RL 阶段可能减弱的能力。

![](https://substack-post-media.s3.amazonaws.com/public/images/fd03d911-1f68-4ac5-9a07-5a576e377ddf_1999x742.png)

图 31：GLM-5 训练管线。

## 6.5 Qwen3 使用模式融合与推断时截断

Qwen3 已在第 4 节讨论过，因此这里仅概括对本次比较重要的部分。根据 [Qwen3 技术报告](https://www.google.com/url?q=https://arxiv.org/abs/2505.09388&sa=D&source=editors&ust=1784335866765752&usg=AOvVaw3VLUySiiox-X0Vw2QPL80b)，其后训练管线分为四个阶段：长思维链 SFT、推理 RL、思考模式融合和通用 RL。

思考模式融合是投入开关的关键阶段。模型在此通过 SFT 学习混合的思考与非思考样本。`/think` 样本包含推理轨迹，而 `/no_think` 样本以一个空的 `<think></think>` 块开头，后接简短回答。随后的一般 RL 阶段会强化两种行为的指令与格式遵循能力。

Qwen3 还支持硬性思考预算。在请求的阈值处，推理片段会被停止，并在模型继续生成最终答案前插入一条停止思考指令。报告称，这种部分推理行为并未被显式训练，而是在思考模式融合后涌现。

这使 Qwen3 同时具备习得的开关和推断时预算。它与 DeepSeek V4 和 Nemotron 的方案类似，但更为简单。

## 6.6 Inkling 以连续投入值为条件进行 RL

Inkling 已在第 5.3 节讨论过。简而言之，其[技术报告](https://www.google.com/url?q=https://thinkingmachines.ai/news/introducing-inkling/&sa=D&source=editors&ust=1784335866767327&usg=AOvVaw2Eich3Nl1VH0sM1fJhcs-7)提到，它们使用连续的投入条件值（介于 0.0 和 1.0 之间），而非固定的投入标签。

在一个相对较小的初始 SFT 阶段之后，Inkling 的大部分后训练来自异步 RL，包含超过 3,000 万次 rollout。所需投入被写入系统消息，RL 期间的 token 长度惩罚会依该值调整。如前所述，更高的 token 成本会促使回答更短；更低的 token 成本则让模型有更大空间进行推理。

## 6.7 已知方案概览

下表总结了六份技术报告中实际披露的内容。

![](https://substack-post-media.s3.amazonaws.com/public/images/38ce02e7-fb5d-4047-8a31-a3ddb4f9f82b_1788x1999.png)

图 32：六个具有推理投入设置的开放权重模型，其已披露训练机制与推断控制的比较。

因此，纵观这六个不同的开放权重模型，它们具有共同框架。首先，它们通过 SFT 与聊天模板引入投入模式控制。Qwen3 显式混合思考和非思考样本，而 GLM-5 则加入交错、保留与回合级思考模式。

第二个共同组件是以模式为条件的 RL 阶段，其中上下文窗口和长度惩罚会随请求的投入变化。DeepSeek V4、Nemotron 3 Ultra 和 Inkling 都采用这种方法。

第三种要素是在明确预算下提升稳健性。Nemotron 以随机截断的轨迹训练；Qwen3 能从被强制停止的推理片段继续生成；Kimi 则交替使用受预算约束与不受约束的 RL。这些方法有助于在可用推理长度变化、甚至被截短时保持答案质量。

## 7\. 结论

本文中的开放权重示例通过多种不同机制实现推理投入。相似的标签背后，可能是独立的专家模型、混合 SFT 数据、模式条件化奖励、硬 token 预算，或这些方法的组合。

很难断言哪种方法最好。这些模型的基座检查点、训练数据、后训练算力、基准和服务目标各不相同；其报告也遗漏了受控比较所需的许多细节。（此外，未必存在一种放之四海而皆准的方案：适合交互式助手的方法，可能并不适合长时间运行的编程智能体。）

当然，圣杯是自动投入选择。我们不久前在 GPT 5 的 Auto 模式中见过这一点。这是一个棘手问题，而最终实现可能失多于得，这或许就是它从 UI 中被移除的原因（至少我已经找不到它了）。

我仍希望投入选择会变得更自动化。类似 GPT 5 的 Auto 模式，一个低成本模型或路由器可以根据请求、工具状态以及剩余时间或 token 预算选择模式，同时仍允许用户覆盖选择。如果你想针对延迟、成本或最高性能优化，这种覆盖很有用。

我知道这是一篇很长的文章，主题或许也并不最吸睛。但鉴于 LLM、推理模型和智能体持续被讨论，我认为系统审视推理模型是此前尚未覆盖的内容；希望它能成为一份独特且多少有用的概览！

## 延伸资源

如果你希望亲手实现推理模型背后的核心训练方法，我的 [从零构建推理模型](https://sebastianraschka.com/books/#build-a-reasoning-model-from-scratch) 一书会以代码逐步讲解带可验证奖励的强化学习与推断时扩展。

本文聚焦已训练的推理模型如何支持不同投入模式。这本书则回退一步，展示如何首先将常规 LLM 转换为推理模型。它是[从零构建大语言模型](https://sebastianraschka.com/books/#build-a-large-language-model-from-scratch)的续作，并从该书结束之处开始。

纸质版现已开始发货。

![](https://substack-post-media.s3.amazonaws.com/public/images/5c56e72d-2f5c-4104-970e-c43dd1965568_1197x1500.jpeg)

从零构建推理模型 \[ Manning \] \[ Amazon \]

如果你喜欢我此前的[从零构建大语言模型](https://amzn.to/4fqvn0D)一书，这本书实质上是其续作，从零实现推断时扩展技术与强化学习算法。

如果你愿意支持未来此类长篇文章，请考虑[成为付费订阅者](https://magazine.sebastianraschka.com/subscribe)。这有助于我持续撰写这些独立深度文章，并分享配套的代码、图表和实验。
