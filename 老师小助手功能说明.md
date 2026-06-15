# 老师助手 Teacher Assistant

基于 DeepSeek API 的 AI 知识库问答系统，支持中英双语，教师可在微信中直接使用。

## 核心功能

### 1. AI 知识问答
- 上传教学/制度文档后，老师可以直接提问，AI 根据文档内容回答
- 支持中文和英文，右上角一键切换
- 每条回复开头附带免责声明

### 2. 知识库管理（需密码）
- 分为 **教学** 和 **制度** 两个类目，文件按类目归类
- **上传**：点 ⚙️ → 选类目 → 上传 .txt / .md 文件
- **删除**：点 ⚙️ → 选类目 → 点文件旁的 🗑 删除
- 上传/删除后自动刷新知识库，无需重启

### 3. 多端访问
- 电脑微信 / 浏览器直接打开链接即可使用
- 无需安装任何软件

## 部署架构

```
用户（微信/浏览器） → Railway 云服务器 → DeepSeek API
                           ↓
                      知识库文件（云端存储）
```

## 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI + Uvicorn |
| 前端 | 原生 HTML/CSS/JS |
| AI 模型 | DeepSeek API |
| 知识库检索 | TF-IDF + jieba 中文分词 |
| 部署平台 | Railway |
| 代码托管 | GitHub |

## 配置文件

`config.py` 中可修改：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | 已配置 |
| `ADMIN_PASSWORD` | 管理密码（上传/删除文件用） | WH0804 |
| `DISCLAIMER_ZH` | 中文免责声明文字 | 小助手刚上岗... |
| `DISCLAIMER_EN` | 英文免责声明文字 | Disclaimer: ... |

## 目录结构

```
老师小助手/
├── config.py              # 配置文件
├── web_app.py             # Web 服务器（主程序）
├── knowledge_base.py      # 知识库引擎（TF-IDF 检索）
├── llm_engine.py          # AI 引擎（DeepSeek API）
├── requirements.txt       # Python 依赖
├── templates/
│   └── chat.html          # 聊天页面
├── knowledge/
│   ├── 教学/              # 教学类文档
│   │   └── 北极星指标口径.txt
│   └── 制度/              # 制度类文档
│       └── 示例-教师手册.txt
└── README.md              # 本文件
```

## 本地开发

```bash
pip install -r requirements.txt
python web_app.py
```

## 使用流程

1. 打开链接进入聊天页面
2. 在输入框提问，AI 根据已上传的文档回答
3. 管理员点 ⚙️ → 输入密码 → 管理知识库文件
4. 上传新文档后立即生效，AI 即可回答新内容
