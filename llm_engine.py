"""
AI 模型引擎 - 支持 DeepSeek API 和 Ollama 本地模型
支持中英双语和多轮对话
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LLMEngine:

    def __init__(self, config):
        self.config = config
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        from openai import OpenAI

        if self.config.USE_DEEPSEEK:
            self._client = OpenAI(
                api_key=self.config.DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com",
            )
            logger.info("使用 DeepSeek API")
        elif self.config.USE_OLLAMA:
            self._client = OpenAI(
                api_key="ollama",
                base_url=f"{self.config.OLLAMA_BASE_URL}/v1",
            )
            logger.info(f"使用 Ollama: {self.config.OLLAMA_MODEL}")
        else:
            raise ValueError("请启用 USE_DEEPSEEK 或 USE_OLLAMA")

        return self._client

    def ask(
        self,
        question: str,
        context: str = "",
        language: str = "zh",
        history: list = None,
    ) -> str:
        try:
            client = self._get_client()

            if self.config.USE_DEEPSEEK:
                model = self.config.DEEPSEEK_MODEL
            else:
                model = self.config.OLLAMA_MODEL

            # 选择语言对应的 prompt
            if language == "en":
                prompt_template = self.config.BOT_PROMPT_EN
            else:
                prompt_template = self.config.BOT_PROMPT_ZH

            # 格式化对话历史
            history_text = ""
            if history:
                lines = []
                for msg in history[-6:]:
                    role = "User" if msg["role"] == "user" else "Assistant"
                    lines.append(f"{role}: {msg['content']}")
                history_text = "\n".join(lines)

            if not history_text:
                history_text = "(无 / None)"

            context_text = context if context else "(无相关知识 / No relevant knowledge found)"

            prompt = prompt_template.format(
                context=context_text,
                history=history_text,
                question=question,
            )

            messages = [{"role": "user", "content": prompt}]

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                stream=False,
            )

            answer = response.choices[0].message.content

            if self.config.USE_DEEPSEEK:
                total_tokens = response.usage.total_tokens
                logger.info(f"DeepSeek 消耗 {total_tokens} tokens")

            return answer

        except Exception as e:
            logger.error(f"AI 模型调用失败: {e}")
            if language == "en":
                return f"Sorry, I'm having trouble answering right now. Error: {str(e)}"
            return f"抱歉，我暂时无法回答这个问题（AI 服务异常: {str(e)}）"

    def check_connection(self) -> tuple:
        try:
            client = self._get_client()
            if self.config.USE_DEEPSEEK:
                model = self.config.DEEPSEEK_MODEL
                msg = "DeepSeek API 连接正常"
            else:
                model = self.config.OLLAMA_MODEL
                msg = f"Ollama ({model}) 连接正常"

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "hello"}],
                max_tokens=10,
                stream=False,
            )
            if response.choices:
                return True, msg
            return False, "模型返回为空"

        except Exception as e:
            err = str(e)
            if "401" in err or "Authentication" in err:
                return False, "API Key 无效，请检查"
            if "402" in err or "Insufficient Balance" in err:
                return False, "API 余额不足，请充值"
            return False, f"连接失败: {e}"
