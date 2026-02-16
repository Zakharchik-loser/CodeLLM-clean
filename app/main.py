import os
import redis
from fastapi import FastAPI,Depends,HTTPException,Header
import ollama
from app.chat import router as chat_router
from redis.asyncio import Redis

app = FastAPI()

redis_client = Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)


def load_api_keys():
    keys=redis_client.hgetall("api:keys")
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

    response = ollama.chat(
        model="mistral",
        messages=[{"role": "user", "content": prompt}]
    )

    return {"response": response["message"]["content"]}



@app.get("/Help",tags=["Get help,execute to see info"])
def help():
    return "Type here on tg - @Mq.T_T"
