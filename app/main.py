import asyncio
import os
from fileinput import filename

import redis
import tavily
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Header, APIRouter
import ollama
import requests
import base64

from pydantic import BaseModel

from app.chat import router as chat_router
from io import BytesIO
from PIL import Image
import uuid
from redis.asyncio import Redis
from tavily import TavilyClient
import requests
load_dotenv()


app = FastAPI()

redis_client = Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_KEY"))

async def load_api_keys():
    keys= await redis_client.hgetall("api:keys")
    if not keys:
        raise RuntimeError("No API keys were found in Redis")
    return {k:int(v) for k,v in keys.items()}






app.include_router(chat_router)




async def verify_api_key(x_api_key: str = Header(...)):
    credits=await redis_client.hget("api:keys",x_api_key)

    if credits is None:
        raise HTTPException(status_code=401,detail="Invalid Api key")


    if int(credits) <= 0:
        raise HTTPException(status_code=403,detail="No credits left")

    return x_api_key



def need_web_search(prompt:str) -> bool:
    keywords = ["today","latest","recent","news",
    "weather","price","current","now"]
    return any(word in prompt.lower() for word in keywords)


def clean_text(text: str) -> str:
    lines = text.split("\n")
    cleaned = []

    for line in lines:
        line = line.strip()
        if len(line) < 20:
            continue
        if "continue" in line.lower():
            continue
        if "subscribe" in line.lower():
            continue
        cleaned.append(line)

    return "\n".join(cleaned)

def simple_score(query: str, text: str) -> int:
    score = 0

    for word in query.lower().split():
        if word in text.lower():
            score += 1
    return score





@app.post("/generate",tags=["Ask mistral AI whatever you want to"])
async def generate(prompt: str, x_api_key: str = Depends(verify_api_key)):

    new_credits = await redis_client.hincrby(
        "api:keys",
        x_api_key,
        -1
    )

    if new_credits < 0:
        await redis_client.hincrby("api:keys", x_api_key, 1)
        raise HTTPException(status_code=403, detail="Credits are cooked")

    context = ""
    processed = []
    if need_web_search(prompt):
        search_results = await asyncio.to_thread(tavily_client.search,prompt)
        results = search_results.get("results", [])


        try:
            for r in results:
                content = clean_text(r.get("content", ""))
                if content:
                    processed.append({
                        "text": content,
                        "score": simple_score(prompt, content)
                    })
        except Exception as e:
            print("Error processing results:", e)

        processed = sorted(processed, key=lambda x: x["score"], reverse=True)

    top_chunks = [x["text"] for x in processed[:3]]

    context = "\n\n---\n\n".join(top_chunks)

    final_prompt = f"""
   You are a factual assistant.

    Rules:
    - Use ONLY the provided context if it is relevant
    - If the context does not contain the answer, say you don't know
    - Do NOT invent facts
    - Be concise
    Context:
    {context if context else "No additional context provided."}

    Question:
    {prompt}
    """
    response = await asyncio.to_thread(
            ollama.chat,
            model="mistral",
            messages=[{"role": "user", "content": final_prompt}]
        )
    return {"response": response["message"]["content"], "model": response["model"]}



FORGE_URL = "http://127.0.0.1:7860"

OUTPUT_DIR = "generated"
os.makedirs(OUTPUT_DIR, exist_ok=True)


FORGE_URL = "http://127.0.0.1:7860"

class Model_config(BaseModel):
    prompt: str
    negative_prompt: str = ""
    steps: int = 20
    width: int = 896
    height: int = 1152
    cfg_scale: int = 1
    distilled_cfg_scale: float = 3.5
    sampler_name: str = "DPM++ 2M"


@app.post("/generate-image",tags=["Generate an image with a model"])
def generate_image(req: Model_config):
    images = {
        "prompt":req.prompt,
        "negative_prompt":req.negative_prompt,
        "steps":req.steps,
        "width":req.width,
        "height":req.height,
        "cfg_scale":req.cfg_scale,
        "sampler_name":req.sampler_name

    }
    url = requests.post(
        f"{FORGE_URL}/sdapi/v1/txt2img",
        json=images,
        timeout=600
    )
    url.raise_for_status()
    result = url.json()

    saved_files = []

    for i in result["images"]:
        image_data = base64.b64decode(i.split(",",1)[-1])
        image = Image.open(BytesIO(image_data))
        filename = f"{uuid.uuid4()}.png"
        filepath = os.path.join(OUTPUT_DIR,filename)

        image.save(filepath)
        saved_files.append(filepath)

    return {
        "success":True,
        "images": saved_files
    }

@app.get("/Help",tags=["Get help,execute to see info"])
def help():
    return "Type here on tg - @Mq.T_T"



