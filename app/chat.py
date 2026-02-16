from fastapi import APIRouter
from pydantic import BaseModel

from app.shcema import ChatResponse, ChatRequest
from app.lang_graph import graph

router = APIRouter(prefix="/chat", tags=["chat"])



@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest):
    state = req.state or {
        "messages": [],
        "message_type": None
    }

    if "messages" not in state:
        state["messages"] = []


    if "messages_type" not in state:
        state["message_type"] = None


    state["messages"].append({
        "role": "user",
        "content": req.message
    })

    new_state = graph.invoke(state)

    reply = new_state["messages"][-1].content

    return {
        "state": new_state
    }
