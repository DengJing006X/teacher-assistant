"""
LLM engine for the H5 test version.
"""

import logging


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
            logger.info("Using DeepSeek API")
        elif self.config.USE_OLLAMA:
            self._client = OpenAI(
                api_key="ollama",
                base_url=f"{self.config.OLLAMA_BASE_URL}/v1",
            )
            logger.info("Using Ollama model: %s", self.config.OLLAMA_MODEL)
        else:
            raise ValueError("Either USE_DEEPSEEK or USE_OLLAMA must be enabled")

        return self._client

    def ask(self, question: str, context: str = "", language: str = "zh", history: list = None) -> str:
        try:
            client = self._get_client()
            model = self.config.DEEPSEEK_MODEL if self.config.USE_DEEPSEEK else self.config.OLLAMA_MODEL

            prompt_template = self.config.BOT_PROMPT_EN if language == "en" else self.config.BOT_PROMPT_ZH

            history_lines = []
            for msg in (history or [])[-6:]:
                role = "User" if msg["role"] == "user" else "Assistant"
                history_lines.append(f"{role}: {msg['content']}")
            history_text = "\n".join(history_lines) if history_lines else "(None)"

            prompt = prompt_template.format(
                context=context if context else "(No relevant knowledge found)",
                history=history_text,
                question=question,
                scope_notice=self.config.TEST_SCOPE_NOTICE_EN if language == "en" else self.config.TEST_SCOPE_NOTICE_ZH,
                unhit_reply=self.config.UNHIT_REPLY_EN if language == "en" else self.config.UNHIT_REPLY_ZH,
            )

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1200,
                stream=False,
            )

            answer = response.choices[0].message.content.strip()
            if self.config.USE_DEEPSEEK and getattr(response, "usage", None):
                logger.info("DeepSeek tokens used: %s", response.usage.total_tokens)

            return answer
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            if language == "en":
                return "Sorry, the AI service is temporarily unavailable. Please try again later."
            return "抱歉，AI 服务暂时不可用，请稍后再试。"

    def check_connection(self) -> tuple:
        try:
            client = self._get_client()
            model = self.config.DEEPSEEK_MODEL if self.config.USE_DEEPSEEK else self.config.OLLAMA_MODEL
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "hello"}],
                max_tokens=10,
                stream=False,
            )
            if response.choices:
                return True, "Model connection is ready"
            return False, "Model returned empty content"
        except Exception as e:
            return False, f"Connection failed: {e}"
