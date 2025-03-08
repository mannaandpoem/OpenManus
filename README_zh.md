[English](README.md) | 简体中文

<p align="left">
    <a href="https://discord.gg/6dn7Sa3a"><img src="https://dcbadge.vercel.app/api/server/DYn29wFk9z?style=flat" alt="Discord Follow"></a>
</p>

# OpenManus 🙋

Manus 非常棒，但 OpenManus 无需邀请码即可实现任何创意 🛫！

我们来自 [@MetaGPT](https://github.com/geekan/MetaGPT) 的团队成员 [@mannaandpoem](https://github.com/mannaandpoem) [@XiangJinyu](https://github.com/XiangJinyu) [@MoshiQAQ](https://github.com/MoshiQAQ) [@didiforgithub](https://github.com/didiforgithub) 在 3 小时内完成了开发！

这是一个简洁的实现方案，欢迎任何建议、贡献和反馈！

用 OpenManus 开启你的智能体之旅吧！

## 项目演示

<video src="https://private-user-images.githubusercontent.com/61239030/420168772-6dcfd0d2-9142-45d9-b74e-d10aa75073c6.mp4?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3NDEzMTgwNTksIm5iZiI6MTc0MTMxNzc1OSwicGF0aCI6Ii82MTIzOTAzMC80MjAxNjg3NzItNmRjZmQwZDItOTE0Mi00NWQ5LWI3NGUtZDEwYWE3NTA3M2M2Lm1wND9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUFWQ09EWUxTQTUzUFFLNFpBJTJGMjAyNTAzMDclMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjUwMzA3VDAzMjIzOVomWC1BbXotRXhwaXJlcz0zMDAmWC1BbXotU2lnbmF0dXJlPTdiZjFkNjlmYWNjMmEzOTliM2Y3M2VlYjgyNDRlZDJmOWE3NWZhZjE1MzhiZWY4YmQ3NjdkNTYwYTU5ZDA2MzYmWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0In0.UuHQCgWYkh0OQq9qsUWqGsUbhG3i9jcZDAMeHjLt5T4" data-canonical-src="https://private-user-images.githubusercontent.com/61239030/420168772-6dcfd0d2-9142-45d9-b74e-d10aa75073c6.mp4?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3NDEzMTgwNTksIm5iZiI6MTc0MTMxNzc1OSwicGF0aCI6Ii82MTIzOTAzMC80MjAxNjg3NzItNmRjZmQwZDItOTE0Mi00NWQ5LWI3NGUtZDEwYWE3NTA3M2M2Lm1wND9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUFWQ09EWUxTQTUzUFFLNFpBJTJGMjAyNTAzMDclMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjUwMzA3VDAzMjIzOVomWC1BbXotRXhwaXJlcz0zMDAmWC1BbXotU2lnbmF0dXJlPTdiZjFkNjlmYWNjMmEzOTliM2Y3M2VlYjgyNDRlZDJmOWE3NWZhZjE1MzhiZWY4YmQ3NjdkNTYwYTU5ZDA2MzYmWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0In0.UuHQCgWYkh0OQq9qsUWqGsUbhG3i9jcZDAMeHjLt5T4" controls="controls" muted="muted" class="d-block rounded-bottom-2 border-top width-fit" style="max-height:640px; min-height: 200px"></video>

## 安装指南

1. 创建新的 conda 环境：

```bash
conda create -n open_manus python=3.12
conda activate open_manus
```

2. 克隆仓库：

```bash
git clone https://github.com/mannaandpoem/OpenManus.git
cd OpenManus
```

3. 安装依赖：

```bash
pip install -r requirements.txt
```

## 配置说明

OpenManus 需要配置使用的 LLM API，请按以下步骤设置：

1. 在 `config` 目录创建 `config.toml` 文件（可从示例复制）：

```bash
cp config/config.example.toml config/config.toml
```

2. 编辑 `config/config.toml` 添加 API 密钥和自定义设置：

```toml
# 全局 LLM 配置
[llm]
model = "gpt-4o"
base_url = "https://api.openai.com/v1"
api_key = "sk-..."  # 替换为真实 API 密钥
max_tokens = 4096
temperature = 0.0

# 可选特定 LLM 模型配置
[llm.vision]
model = "gpt-4o"
base_url = "https://api.openai.com/v1"
api_key = "sk-..."  # 替换为真实 API 密钥
```

## docker 启动

[docker](docker.md)

## 快速启动

一行命令运行 OpenManus：

```bash
python main.py
```

然后通过终端输入你的创意！

如需体验开发中版本，可运行：

```bash
python run_flow.py
```

## 贡献指南

我们欢迎任何友好的建议和有价值的贡献！可以直接创建 issue 或提交 pull request。

或通过 📧 邮件联系 @mannaandpoem：mannaandpoem@gmail.com

## 发展路线

在全面收集了社区成员的反馈后，我们决定采用 3-4 天为周期的迭代模式，逐步实现大家期待的功能。

- [ ] 增强 Planning 能力，优化任务分解和执行逻辑
- [ ] 引入标准化评测，基于 GAIA 和 TAU-Bench，持续评估并优化性能
- [ ] 拓展模型适配，优化低成本应用场景
- [ ] 实现容器化部署，简化安装和使用流程
- [ ] 丰富示例库，增加更多实用案例，包含成功和失败示例的分析
- [ ] 前后端开发，提供用户体验
- [ ] RAG增强，实现外部知识图谱检索与融合机制

## 交流群

加入我们的飞书交流群，与其他开发者分享经验！

<div align="center" style="display: flex; gap: 20px;">
    <img src="assets/community_group.jpg" alt="OpenManus 交流群" width="300" />
</div>

## Star 数量

[![Star History Chart](https://api.star-history.com/svg?repos=mannaandpoem/OpenManus&type=Date)](https://star-history.com/#mannaandpoem/OpenManus&Date)

## 致谢

特别感谢 [anthropic-computer-use](https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo)
和 [browser-use](https://github.com/browser-use/browser-use) 为本项目提供的基础支持！

OpenManus 由 MetaGPT 社区的贡献者共同构建，感谢这个充满活力的智能体开发者社区！
