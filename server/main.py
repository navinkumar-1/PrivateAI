from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, PlainTextResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import uuid
from datetime import datetime
from backend.LLM import get_response_from_llm
from backend.chat_store import get_all_chats, create_chat, get_chat, add_message_to_chat

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CHATS_DIR = "./chats"

@app.get("/")
async def root():
    return PlainTextResponse("PrivateAI API")

@app.get("/api/chats")
async def list_chats():
    return get_all_chats()

@app.get("/api/chats/{chat_id}")
async def get_chat_endpoint(chat_id: str):
    chat_data = get_chat(chat_id)
    if not chat_data:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat_data

# New endpoint for creating chats
@app.post("/api/chats")
async def create_chat_endpoint():
    chat_id = create_chat()
    return {"chat_id": chat_id}

@app.post("/api/data")
async def handle_query(request: Request):
    body = await request.json()
    prompt = body.get("prompt")
    chat_id = body.get("chat_id")
    
    if not prompt or not prompt.strip():
        raise HTTPException(status_code=400, detail="Empty prompt")

    # Get chat history
    chat_data = get_chat(chat_id) if chat_id else None
    messages = chat_data.get("messages", []) if chat_data else []
    
    # Build conversation context from last 3 messages
    context = "\n".join([f"User: {msg['query']}\nAI: {msg['response']}" 
                       for msg in messages[-3:]])
    
    # Create chat if none exists
    if not chat_id or not chat_data:
        chat_id = create_chat()
    
    # Create final prompt with history
    full_prompt = f"{context}\nUser: {prompt}\nAI:" if context else prompt

    # Text response handling
    def generate():
        full_response = ""
        # Pass full_prompt to LLM instead of raw prompt
        for chunk in get_response_from_llm(full_prompt):
            try:
                if isinstance(chunk, bytes):
                    chunk = chunk.decode("utf-8")
                chunk_dict = json.loads(chunk)
                text = chunk_dict.get("response", "")
                full_response += text
                yield text
            except Exception as e:
                print(f"Error processing chunk: {e}")
        add_message_to_chat(chat_id, prompt, full_response)

    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
