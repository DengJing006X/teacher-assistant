"""
钉钉老师助手 - 主程序
======================
一个基于知识库的钉钉机器人，帮助新老师解答工作问题。

启动方式：
    python main.py
"""

import os
import sys
import json
import logging
from pathlib import Path

# 确保项目根目录在 Python 路径中
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

import config as app_config
from knowledge_base import KnowledgeBase
from llm_engine import LLMEngine

# 日志配置
logging.basicConfig(
    level=getattr(logging, app_config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class TeacherBot:
    """钉钉老师助手机器人"""

    def __init__(self):
        self.config = app_config
        self.knowledge_base = KnowledgeBase(self.config)
        self.llm = LLMEngine(self.config)

    def process_question(self, question: str) -> str:
        """
        处理用户问题：
        1. 知识库检索
        2. 调用 AI 生成回答
        """
        logger.info(f"收到问题: {question}")

        # 检索知识库
        results = self.knowledge_base.search(question)

        if results:
            context_parts = []
            for content, similarity, filename in results:
                context_parts.append(
                    f"[来自文档: {filename}]\n{content}"
                )
            context = "\n\n---\n\n".join(context_parts)
            logger.info(f"检索到 {len(results)} 个相关片段")
        else:
            context = ""
            logger.info("未检索到相关信息")

        # 生成回答
        answer = self.llm.ask(question, context)
        logger.info(f"生成回答完成 ({len(answer)} 字)")
        return answer

    def check_setup(self) -> list[str]:
        """检查配置是否正确，返回问题列表"""
        issues = []

        # 检查钉钉配置
        if "your_client_id" in self.config.DINGTALK_CLIENT_ID.lower():
            issues.append("请在 config.py 中填写正确的 DINGTALK_CLIENT_ID")
        if "your_client_secret" in self.config.DINGTALK_CLIENT_SECRET.lower():
            issues.append("请在 config.py 中填写正确的 DINGTALK_CLIENT_SECRET")

        # 检查 DeepSeek 配置
        if self.config.USE_DEEPSEEK:
            if "your_deepseek_api_key" in self.config.DEEPSEEK_API_KEY.lower():
                issues.append("请在 config.py 中填写正确的 DEEPSEEK_API_KEY")

        # 检查知识库
        kb_path = self.config.KNOWLEDGE_DIR
        doc_files = list(kb_path.glob("*"))
        md_txt_files = [
            f for f in doc_files
            if f.suffix.lower() in [".md", ".txt"]
        ]
        if not md_txt_files:
            issues.append(
                f"knowledge 目录为空，请放入 .md 或 .txt 文档\n"
                f"  目录路径: {kb_path}"
            )

        return issues

    def run(self):
        """启动钉钉 Stream 模式机器人"""
        issues = self.check_setup()
        if issues:
            logger.error("配置检查发现问题：")
            for issue in issues:
                logger.error(f"  - {issue}")
            logger.error("请修复后重新启动")
            return

        # 初始化知识库
        logger.info("正在初始化知识库...")
        self.knowledge_base.initialize()
        doc_count = self.knowledge_base.get_document_count()
        chunk_count = self.knowledge_base.get_chunk_count()
        logger.info(f"知识库就绪: {doc_count} 个文档, {chunk_count} 个文本片段")

        # 测试 AI 连接
        logger.info("正在测试 AI 模型连接...")
        ok, msg = self.llm.check_connection()
        if ok:
            logger.info(f"AI 模型连接测试通过: {msg}")
        else:
            logger.warning(f"AI 模型连接测试失败: {msg}")
            logger.warning("机器人将继续启动，但回答问题可能会失败")

        # 启动钉钉 Stream 客户端
        logger.info("=" * 50)
        logger.info("正在连接钉钉...")
        logger.info("机器人已启动，等待消息...")
        logger.info("=" * 50)

        try:
            import dingtalk_stream

            credential = dingtalk_stream.Credential(
                self.config.DINGTALK_CLIENT_ID,
                self.config.DINGTALK_CLIENT_SECRET,
            )
            client = dingtalk_stream.DingTalkStreamClient(credential)

            @client.register_callback(
                dingtalk_stream.ChatbotMessage
            )
            def on_message(message: dingtalk_stream.ChatbotMessage):
                """处理收到的消息"""
                try:
                    question = message.text.content.strip()
                    sender = message.sender_nick or message.sender_id
                    logger.info(f"来自 [{sender}] 的消息: {question}")

                    answer = self.process_question(question)

                    # 回复消息
                    client.reply_message(
                        dingtalk_stream.Message(
                            conversation_type=message.conversation_type,
                            conversation_id=message.conversation_id,
                            sender_id=message.sender_id,
                        ),
                        dingtalk_stream.ChatbotMessage(
                            text=dingtalk_stream.TextContent(answer)
                        ),
                    )
                    logger.info(f"已回复 [{sender}]: {answer[:50]}...")

                except Exception as e:
                    logger.error(f"处理消息失败: {e}", exc_info=True)

            client.start_forever()

        except ImportError:
            logger.error(
                "缺少 dingtalk-stream 库，请运行: "
                "pip install dingtalk-stream"
            )
        except Exception as e:
            logger.error(f"启动机器人失败: {e}", exc_info=True)


def main():
    """入口函数"""
    bot = TeacherBot()
    bot.run()


if __name__ == "__main__":
    main()
