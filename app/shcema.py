from pydantic import BaseModel


class ChatRequest(BaseModel):
    message:str
    state: dict | None = None



class ChatResponse(BaseModel):
    state:dict


