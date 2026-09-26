from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OLLAMA_URL = "http://localhost:11434"
PROVIDERS = {
    "ollama": {
        "label": "本地 Ollama",
        "url": OLLAMA_URL,
        "env": "",
        "models": (),
    },
    "qwen": {
        "label": "通义千问",
        "url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "env": "DASHSCOPE_API_KEY",
        "models": ("qwen3.8-flash", "qwen3.7-plus", "qwen-plus", "qwen-turbo"),
    },
    "deepseek": {
        "label": "DeepSeek",
        "url": "https://api.deepseek.com/v1",
        "env": "DEEPSEEK_API_KEY",
        "models": ("deepseek-v4-flash", "deepseek-chat", "deepseek-reasoner"),
    },
}

SYSTEM_PROMPT = """你是 Radar Flow Analyzer 的雷达数据链路学习与工程辅助助手。请使用中文回答，并严格遵守：
1. 优先依据当前工具页面、可见数据、参考参数和已展示结果回答。
2. 明确区分可观测数据、处理链推导、教学仿真、真实模组接口和当前不可验证内容。
3. 不虚构真实硬件测试结果、厂商内部算法、未提供的采样参数、目标真值或性能指标。
4. 解释雷达处理时，应围绕 ADC/IQ、Range FFT、Doppler FFT、Range-Doppler、Candidate/Feature 和 Presence 的数据层级说明。
5. 如需推测，必须明确标记为推测，并说明还需要哪一层数据才能验证。"""


class AiError(RuntimeError):
    pass


def environment_key(provider: str) -> str:
    env_name = str(PROVIDERS[provider]["env"])
    return os.environ.get(env_name, "") if env_name else ""


@dataclass(frozen=True, slots=True)
class AiClient:
    provider: str
    api_key: str = ""
    timeout_seconds: float = 90.0

    def list_ollama_models(self) -> list[str]:
        payload = self._request("GET", f"{OLLAMA_URL}/api/tags")
        return [
            str(model["name"])
            for model in payload.get("models", [])
            if isinstance(model, dict) and model.get("name")
        ]

    def stream_chat(self, model: str, question: str, context: str) -> Iterator[str]:
        if self.provider == "ollama":
            yield from self._stream_ollama(model, question, context)
            return
        provider = PROVIDERS.get(self.provider)
        if provider is None:
            raise AiError(f"未知的 AI 提供商：{self.provider}")
        if not self.api_key:
            raise AiError(f"请填写 API Key 或设置环境变量 {provider['env']}。")
        yield from self._stream_openai_compatible(model, question, context, provider)

    def _stream_ollama(self, model: str, question: str, context: str) -> Iterator[str]:
        payload = {
            "model": model,
            "stream": True,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{context}\n\n用户问题：{question}"},
            ],
        }
        request = Request(
            f"{OLLAMA_URL}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                for raw_line in response:
                    if not raw_line.strip():
                        continue
                    message = json.loads(raw_line.decode("utf-8")).get("message", {})
                    if isinstance(message, dict) and message.get("content"):
                        yield str(message["content"])
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise AiError(f"Ollama 请求失败（HTTP {error.code}）：{detail}") from error
        except URLError as error:
            raise AiError(f"无法连接 Ollama：{error.reason}") from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise AiError("Ollama 返回了无法解析的数据。") from error

    def _stream_openai_compatible(
        self,
        model: str,
        question: str,
        context: str,
        provider: dict[str, object],
    ) -> Iterator[str]:
        base_url = str(provider["url"]).rstrip("/")
        payload = {
            "model": model,
            "stream": True,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{context}\n\n用户问题：{question}"},
            ],
        }
        request = Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    choices = json.loads(data).get("choices", [])
                    if choices and isinstance(choices[0], dict):
                        delta = choices[0].get("delta", {})
                        if isinstance(delta, dict) and delta.get("content"):
                            yield str(delta["content"])
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise AiError(f"{provider['label']} 请求失败（HTTP {error.code}）：{detail}") from error
        except URLError as error:
            raise AiError(f"无法连接 {provider['label']}：{error.reason}") from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise AiError(f"{provider['label']} 返回了无法解析的数据。") from error

    def _request(self, method: str, url: str) -> dict:
        try:
            with urlopen(Request(url, method=method), timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise AiError(f"无法连接 Ollama（HTTP {error.code}）：{detail}") from error
        except URLError as error:
            raise AiError(f"无法连接 Ollama：{error.reason}") from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise AiError("Ollama 返回了无法解析的数据。") from error
        if not isinstance(payload, dict):
            raise AiError("Ollama 返回格式不正确。")
        return payload
