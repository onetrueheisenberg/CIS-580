# import requests
# import json

# url = "https://api.awanllm.com/v1/completions"

# payload = json.dumps({
#   "model": "Meta-Llama-3-8B-Instruct",
#   "prompt": "What's happening in this commit: https://github.com/ipedrazas/drone-helm/commit/72dc20f4b5e08b68e94950692707d599424c4394",
#   "repetition_penalty": 1.1,
#   "temperature": 0.7,
#   "top_p": 0.9,
#   "top_k": 40,
#   "max_tokens": 1024,
#   "stream": True
# })
# headers = {
#   'Content-Type': 'application/json',
#   'Authorization': f"Bearer 3c5ac04c-b1c3-485f-a301-43db9e486081"
# }

# response = requests.request("POST", url, headers=headers, data=payload)
# print(response.text)
#pip install groq cycls
# from cycls import Cycls
# from groq import AsyncGroq

# # cycls = Cycls()
# groq = AsyncGroq(api_key="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")
# #main LLM function
# async def groq_llm(x):
#     stream = await groq.chat.completions.create(
#         messages=x,
#         model="llama-3.1-70b-versatile",
#         temperature=0.5, max_tokens=1024, top_p=1, stop=None, 
#         stream=True,
#     )
#     async def event_stream():
#         async for chunk in stream:
#             content = chunk.choices[0].delta.content
#             if content:
#                 yield content
#     return event_stream()

# # @cycls("@my-llama") # add your app name here to get your app link once you run it 🦙
# history = {}
# def groq_app(message):
#     #history and memory
#     history = [{"role": "system", "content": "you are a helpful assistant."}]
#     history +=  message.history
#     history += [{"role": "user", "content": message.content}]
#     print(groq_llm(history))
# print(groq_app("Hello"))
# import os

# from groq import Groq

# client = Groq(
#     api_key="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",
# )

# chat_completion = client.chat.completions.create(
#     messages=[
#         {
#             "role": "user",
#             "content": "Explain what is being donr in this commit: https://github.com/OpenDroneMap/WebODM/commit/04aa66c47803707ad3aff50978e1347818ac29f2",
#         }
#     ],
#     model="llama-3.3-70b-versatile",
# )

# print(chat_completion.choices[0].message.content)
curl https://api.groq.com/openai/v1/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer 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" \
-d '{
  "model": "llama-3.3-70b-versatile",
  "messages": [
    {
      "role": "user",
      "content": "Explain what is being donr in this commit: https://github.com/OpenDroneMap/WebODM/commit/04aa66c47803707ad3aff50978e1347818ac29f2"
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_current_weather",
        "description": "Get the current weather in a given location",
        "parameters": {
          "type": "object",
          "properties": {
            "location": {
              "type": "string",
              "description": "The city and state, e.g. San Francisco, CA"
            },
            "unit": {
              "type": "string",
              "enum": ["celsius", "fahrenheit"]
            }
          },
          "required": ["location"]
        }
      }
    }
  ],
  "tool_choice": "auto"
}'

# cycls.push()