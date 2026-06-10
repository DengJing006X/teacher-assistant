# 钉钉老师助手 🎓

一个基于知识库的钉钉机器人，帮助新老师解答工作中的各种问题。

## 功能特点

- **智能问答**：基于你提供的文档，自动回答老师的问题
- **数据安全**：所有资料存储本地，不外传
- **简单易用**：写好文档就能用，无需编程
- **费用极低**：推荐 DeepSeek API，一个月不到1块钱

---

## 一、准备工作（30分钟）

### 1.1 安装 Python

> 如果你的电脑已有 Python 3.9+，请跳过这一步。

1. 打开 https://www.python.org/downloads/
2. 下载 Python 3.11 或 3.12
3. 安装时 **一定要勾选** "Add Python to PATH"
4. 安装完成后，打开命令提示符，输入 `python --version`，看到版本号即成功

### 1.2 准备知识库文档

将你的资料文档（如教师手册、规章制度、教学口径等）放到 `knowledge` 文件夹中。

支持格式：
- `.md` 文件（Markdown 格式）
- `.txt` 文件（纯文本）

> 💡 **建议**：将文档整理成清晰的 Markdown 格式，效果最好。
> 可以用 Word 打开你的文档，另存为纯文本 (.txt) 再放入。

---

## 二、配置（5分钟）

### 2.1 注册 DeepSeek API（推荐方案）

> 如果要用免费本地模型，请看 2.2 节。

1. 打开 https://platform.deepseek.com/ 注册账号
2. 进入 "API Keys" 页面，创建一个新的 API Key
3. 复制 API Key（以 `sk-` 开头）

### 2.2 或者安装 Ollama（完全免费）

> i5 电脑可以运行小模型，速度可能稍慢。

1. 下载 Ollama：https://ollama.com/
2. 安装后，打开命令提示符，运行：
   ```
   ollama pull qwen2.5:3b
   ```
3. 等待下载完成（约 2GB）

### 2.3 修改配置文件

用记事本打开 `config.py`，修改以下内容：

```python
# 必填：钉钉配置（如何获取见下文第 2.4 节）
DINGTALK_CLIENT_ID = "你的ClientId"
DINGTALK_CLIENT_SECRET = "你的ClientSecret"

# 二选一：如果使用 DeepSeek
USE_DEEPSEEK = True
DEEPSEEK_API_KEY = "你的DeepSeek API Key"

# 二选一：如果使用 Ollama
USE_OLLAMA = False
```

> 只需修改这 4 行，其他不要动。

### 2.4 创建钉钉机器人

1. 打开 https://open.dingtalk.com/ 登录（用钉钉扫描）
2. 点击右上角 "创建应用" → "企业内部应用"
3. 填写应用名称（如"老师助手"），创建
4. 在左侧菜单找到 **"凭证与基础信息"**
   - 复制 **Client ID**（原 AppKey）
   - 复制 **Client Secret**（原 AppSecret）
   - 粘贴到 `config.py` 对应位置
5. 在左侧菜单找到 **"机器人与消息推送"**
   - 点击 "启用机器人"
   - 消息接收模式选择 **"Stream模式"**
   - 保存

---

## 三、启动机器人

### 方式一：双击启动（推荐）

双击 `start.bat` 文件，等待自动安装依赖和启动。

### 方式二：命令行启动

```bash
# 安装依赖（只需要运行一次）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 启动机器人
python main.py
```

启动成功后，你会看到：
```
==================================================
正在连接钉钉...
机器人已启动，等待消息...
==================================================
```

---

## 四、使用方法

1. 在钉钉中搜索你的机器人名称（如"老师助手"）
2. 发送消息给机器人
3. 机器人会根据知识库内容回答你的问题

### 使用建议

- 问题要具体，比如"新老师的课时费怎么算？"比"工资怎么算"效果更好
- 如果回答不准确，可以调整知识库文档的内容
- 可以随时在 `knowledge` 文件夹中添加/修改文档，重启机器人生效

---

## 五、常见问题

### Q: 启动时下载模型很慢怎么办？

首次启动会下载 embedding 模型（约 400MB），请耐心等待。如果太慢，可以用手机热点试试，或者使用 `pip install sentence-transformers -i https://pypi.tuna.tsinghua.edu.cn/simple` 换国内源。

### Q: 机器人没反应？

1. 检查 config.py 中的钉钉 Client ID 和 Secret 是否正确
2. 检查钉钉开放平台中机器人的"消息接收模式"是否选择了 Stream 模式
3. 查看命令行窗口是否有报错信息

### Q: 如何让机器人回答更准确？

- 知识库文档越清晰、越结构化，效果越好
- 可以在 `config.py` 中调整 `BOT_PROMPT` 来改变回答风格
- 调整 `CHUNK_SIZE`（分块大小）可以改变检索粒度

### Q: 我想让机器人在群里回答问题？

在钉钉开放平台中，将机器人添加到目标群即可。

---

## 项目结构

```
老师小助手/
├── config.py          # 配置文件（你主要修改这里）
├── main.py            # 主程序（不要动）
├── knowledge_base.py  # 知识库引擎（不要动）
├── llm_engine.py      # AI 模型引擎（不要动）
├── requirements.txt   # 依赖清单
├── start.bat          # 一键启动脚本
├── knowledge/         # 存放你的知识库文档
│   ├── 教师手册.md
│   └── 教学制度.txt
└── vector_store/      # 向量数据库（自动生成，不要动）
```
