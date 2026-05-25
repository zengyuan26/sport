"""LLM 工具 — 调用 LLM API 生成内容。优先使用数据库设置，fallback 到环境变量。"""
import os
import json
import logging
import requests

logger = logging.getLogger(__name__)


def _get_config(key, default=''):
    """从数据库 Setting 表读取配置，fallback 到环境变量"""
    try:
        from models import Setting
        s = Setting.query.filter_by(key=key).first()
        if s and s.value:
            return s.value
    except Exception:
        pass
    return os.environ.get(key, default)


def get_llm_config():
    """返回当前生效的 LLM 配置"""
    return {
        'api_key': _get_config('LLM_API_KEY', os.environ.get('LLM_API_KEY', '')),
        'base_url': _get_config('LLM_BASE_URL', os.environ.get('LLM_BASE_URL', 'https://api.deepseek.com/v1')),
        'model': _get_config('LLM_MODEL', os.environ.get('LLM_MODEL', 'deepseek-chat')),
    }


def chat(prompt, temperature=0.8, max_tokens=2000):
    """调用 LLM，返回文本或 None"""
    api_key = _get_config('LLM_API_KEY', os.environ.get('LLM_API_KEY', ''))
    base_url = _get_config('LLM_BASE_URL', os.environ.get('LLM_BASE_URL', 'https://api.deepseek.com/v1'))
    model = _get_config('LLM_MODEL', os.environ.get('LLM_MODEL', 'deepseek-chat'))

    if not api_key:
        logger.error("LLM_API_KEY not configured")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers=headers, json=payload, timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return None


def chat_json(prompt, temperature=0.7, max_tokens=2000):
    """调用 LLM 并解析 JSON 返回。失败返回 None"""
    full_prompt = prompt + '\n\n请直接输出 JSON，不要包含 markdown 代码块标记。注意确保 JSON 完整闭合。'
    text = chat(full_prompt, temperature=temperature, max_tokens=max_tokens)
    if not text:
        return None
    try:
        # Try direct parse first
        return json.loads(text)
    except json.JSONDecodeError:
        # Try extract from markdown code block
        import re
        m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # Try to repair truncated JSON
        result = _repair_json(text)
        if result:
            return result
        logger.error(f"Failed to parse JSON from: {text[:300]}")
        return None


def _repair_json(text):
    """尝试修复被截断的 JSON"""
    import re
    # Remove trailing incomplete strings/keys
    text = text.strip()
    # Count braces
    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')
    # If the last character is part of an incomplete string, find last complete value
    if not text.endswith('}') and not text.endswith(']') and not text.endswith('"'):
        # Try to close by removing the last incomplete element
        last_comma = text.rfind(',')
        if last_comma > 0:
            text = text[:last_comma]
    # Close any open structures
    text += ']' * open_brackets
    text += '}' * open_braces
    # If the text doesn't end with a quote, add one (for truncated string)
    if not text.rstrip().endswith('"'):
        text = text.rstrip() + '"'
        text += ']' * (text.count('[') - text.count(']'))
        text += '}' * (text.count('{') - text.count('}'))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    return None
