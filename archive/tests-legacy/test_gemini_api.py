import os

from google import genai

model = os.environ.get("GEMINI_MODEL", "models/gemini-3-pro-preview")
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    raise SystemExit("GEMINI_API_KEY 未配置")

client = genai.Client(api_key=api_key)

prompt = "请用一句话介绍自己，这是一个连通性测试。"
response = client.models.generate_content(
    model=model,
    contents=[{"role": "user", "parts": [{"text": prompt}]}],
)

print("模型:", model)
print("响应: ", response.text)
