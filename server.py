import uvicorn
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json


# Import your agent class
from my_agents import PreConsulteAgent

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("medforce-server")

# Initialize FastAPI app
app = FastAPI(title="MedForce Hepatology Chat Server")

# Add CORS Middleware (allows your frontend to talk to this server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the Agent
# We instantiate it once so we don't reconnect to GCS/VertexAI on every request
chat_agent = PreConsulteAgent()

# --- Pydantic Models ---

class ChatRequest(BaseModel):
    patient_id: str
    patient_message: str

class ChatResponse(BaseModel):
    patient_id: str
    nurse_response: str
    status: str

# --- Endpoints ---

@app.get("/")
async def root():
    return {"status": "MedForce Server is Running"}

@app.post("/chat", response_model=ChatResponse)
async def handle_chat(payload: ChatRequest):
    """
    Receives a message from the patient, processes it via the PreConsulteAgent,
    updates GCS history, and returns the Nurse/Admin response.
    """
    logger.info(f"Received message from patient: {payload.patient_id}")

    try:
        # Call the logic defined in my_agents.py
        # This function handles reading history, calling Gemini, and saving history
        response_text = await chat_agent.pre_consulte_agent(
            current_user_message=payload.patient_message,
            patient_id=payload.patient_id
        )

        return ChatResponse(
            patient_id=payload.patient_id,
            nurse_response=response_text,
            status="success"
        )

    except FileNotFoundError:
        # This happens if the patient_id folder or pre_consultation_chat.json doesn't exist in GCS
        logger.error(f"Patient data not found for ID: {payload.patient_id}")
        raise HTTPException(
            status_code=404, 
            detail=f"Patient data not found. Please generate ground truth data for ID {payload.patient_id} first."
        )
    
    except Exception as e:
        logger.error(f"Error processing chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/{patient_id}")
async def get_chat_history(patient_id: str):
    """
    Retrieves the full chat history for a specific patient.
    """
    try:
        # Define the path based on your folder structure in my_agents.py
        file_path = f"patient_data/{patient_id}/pre_consultation_chat.json"

        # Read file from GCS using the agent's existing GCS manager
        content_str = chat_agent.gcs.read_file_as_string(file_path)

        if not content_str:
            raise HTTPException(status_code=404, detail="Chat history file is empty or missing.")

        # Parse string back to JSON object to return proper structure
        history_data = json.loads(content_str)

        return history_data

    except Exception as e:
        logger.error(f"Error fetching chat history for {patient_id}: {str(e)}")
        # Check if it's a specific GCS 'Not Found' error if possible, otherwise generic 404
        raise HTTPException(status_code=404, detail=f"Chat history not found for patient {patient_id}")

# --- Run Block ---
if __name__ == "__main__":
    # Run with: python server.py
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)