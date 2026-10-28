"""OpenAI-compatible transport for the existing agent's message/tool contract."""

import json
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit

import httpx


def normalize_base_url(value: str, provider: str) -> str:
    parts = urlsplit(value.strip())
    if (parts.scheme not in ("https", "http") or not parts.hostname
            or parts.username or parts.password or parts.query or parts.fragment):
        raise ValueError("API Base URL ต้องเป็น URL แบบ HTTP(S) ที่ไม่มี credentials, query หรือ fragment")
    path = parts.path.rstrip("/")
    if path.endswith("/models"):
        path = path[:-len("/models")]
    if provider == "anthropic" and path.endswith("/v1"):
        path = path[:-3]
    elif provider == "openai" and not path.endswith("/v1"):
        path += "/v1"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


class ProviderAPIError(RuntimeError):
    def __init__(self, status_code):
        self.status_code = status_code
        messages = {
            401: "API key ไม่ผ่านการยืนยัน กรุณาตรวจ key และ Base URL ของผู้ให้บริการเดียวกัน",
            403: "API key ไม่มีสิทธิ์ใช้ pool หรือโมเดลนี้ กรุณาตรวจสิทธิ์ใน Dashboard",
            404: "ไม่พบ endpoint หรือโมเดล กรุณาตรวจ Base URL และโหลดรายการโมเดลอีกครั้ง",
            429: "ถึงขีดจำกัดการใช้งาน กรุณาตรวจเครดิตและ rate limit ใน Dashboard",
        }
        super().__init__(f"HTTP {status_code}: " + messages.get(
            status_code, "ผู้ให้บริการปฏิเสธคำขอ กรุณาตรวจโมเดลและการตั้งค่าใน Dashboard"
        ))


def _block_dict(block):
    return block if isinstance(block, dict) else vars(block)


def _user_content(blocks):
    content = []
    for block in blocks:
        block = _block_dict(block)
        if block["type"] == "text":
            content.append({"type": "text", "text": block["text"]})
        elif block["type"] == "image":
            source = block["source"]
            content.append({"type": "image_url", "image_url": {
                "url": f"data:{source['media_type']};base64,{source['data']}"
            }})
    return content


def _chat_messages(system, messages):
    converted = [{"role": "system", "content": system}] if system else []
    for message in messages:
        content = message["content"]
        if isinstance(content, str):
            converted.append({"role": message["role"], "content": content})
        elif message["role"] == "assistant":
            blocks = [_block_dict(block) for block in content]
            item = {"role": "assistant", "content": "".join(
                block["text"] for block in blocks if block["type"] == "text"
            ) or None}
            calls = [{"id": block["id"], "type": "function", "function": {
                "name": block["name"], "arguments": json.dumps(block["input"], ensure_ascii=False)
            }} for block in blocks if block["type"] == "tool_use"]
            if calls:
                item["tool_calls"] = calls
            converted.append(item)
        else:
            attachments = []
            for block in content:
                block = _block_dict(block)
                if block["type"] == "tool_result":
                    result = block["content"]
                    if isinstance(result, str):
                        text = result
                    else:
                        text = "\n".join(part["text"] for part in result if part["type"] == "text")
                        images = [part for part in result if part["type"] == "image"]
                        if images:
                            attachments.append({"type": "text", "text": f"Images from tool {block['tool_use_id']}"})
                            attachments.extend(_user_content(images))
                    converted.append({"role": "tool", "tool_call_id": block["tool_use_id"], "content": text})
                else:
                    attachments.extend(_user_content([block]))
            # All parallel tool results must precede the next user message.
            if attachments:
                converted.append({"role": "user", "content": attachments})
    return converted


class OpenAICompatibleClient:
    """Keep the agent loop and graph code shared across API protocols."""

    def __init__(self, api_key, base_url):
        self.messages = self
        self._http = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(180, connect=10), follow_redirects=False,
        )

    def _request(self, method, path, **kwargs):
        response = self._http.request(method, path, **kwargs)
        if not response.is_success:
            raise ProviderAPIError(response.status_code)
        return response.json()

    def list_models(self):
        return [item["id"] for item in self._request("GET", "models").get("data", [])]

    def create(self, *, model, max_tokens, system, messages, tools=None):
        payload = {"model": model, "max_tokens": max_tokens,
                   "messages": _chat_messages(system, messages)}
        # Anthropic's hosted web_search is unavailable here; the existing local
        # google_search tool still searches the web through DuckDuckGo.
        functions = [{"type": "function", "function": {
            "name": tool["name"], "description": tool.get("description", ""),
            "parameters": tool["input_schema"],
        }} for tool in tools or [] if "input_schema" in tool]
        if functions:
            payload["tools"] = functions
        choice = self._request("POST", "chat/completions", json=payload)["choices"][0]
        message = choice["message"]
        blocks = []
        if message.get("content"):
            blocks.append(SimpleNamespace(type="text", text=message["content"]))
        for call in message.get("tool_calls") or []:
            arguments = json.loads(call["function"]["arguments"])
            if not isinstance(arguments, dict):
                raise ValueError("ผู้ให้บริการส่ง arguments ของเครื่องมือที่ไม่ใช่ JSON object")
            blocks.append(SimpleNamespace(type="tool_use", id=call["id"],
                                          name=call["function"]["name"], input=arguments))
        return SimpleNamespace(content=blocks, stop_reason={
            "tool_calls": "tool_use", "length": "max_tokens",
        }.get(choice.get("finish_reason"), "end_turn"))

    def close(self):
        self._http.close()
