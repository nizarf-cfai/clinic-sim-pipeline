import uvicorn
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import json
import base64 # <--- Import base64

# Import your agent class
import my_agents
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

class FileAttachment(BaseModel):
    filename: str
    content_base64: str  # The file bytes encoded as a Base64 string

class ChatRequest(BaseModel):
    patient_id: str
    patient_message: str
    # Changed to accept a list of objects containing the data
    patient_attachments: Optional[List[FileAttachment]] = None 
    patient_form: Optional[dict] = None

class ChatResponse(BaseModel):
    patient_id: str
    nurse_response: dict # Changed from str to dict to handle the rich JSON
    status: str

# --- Endpoints ---

@app.get("/")
async def root():
    return {"status": "MedForce Server is Running"}

@app.post("/chat", response_model=ChatResponse)
async def handle_chat(payload: ChatRequest):
    """
    Receives JSON payload with Base64 encoded files.
    Decodes files -> Saves to GCS -> Passes filenames to Agent.
    """
    logger.info(f"Received message from patient: {payload.patient_id}")

    try:
        # 1. HANDLE FILE UPLOADS (Base64 -> GCS)
        filenames_for_agent = []
        
        if payload.patient_attachments:
            for att in payload.patient_attachments:
                try:
                    # Decode the Base64 string back to bytes
                    # Handle cases where frontend might send "data:image/png;base64,..." header
                    if "," in att.content_base64:
                        header, encoded = att.content_base64.split(",", 1)
                    else:
                        encoded = att.content_base64

                    file_bytes = base64.b64decode(encoded)

                    # Save to GCS
                    file_path = f"patient_data/{payload.patient_id}/raw_data/{att.filename}"
                    
                    # We can try to infer content type from filename extension or header
                    content_type = "application/octet-stream"
                    if att.filename.lower().endswith(".png"): content_type = "image/png"
                    elif att.filename.lower().endswith(".jpg"): content_type = "image/jpeg"
                    elif att.filename.lower().endswith(".pdf"): content_type = "application/pdf"

                    chat_agent.gcs.create_file_from_string(
                        file_bytes, 
                        file_path, 
                        content_type=content_type
                    )
                    
                    # Keep track of just the filename for the agent
                    filenames_for_agent.append(att.filename)
                    logger.info(f"Saved file via Base64: {att.filename}")

                except Exception as e:
                    logger.error(f"Failed to decode file {att.filename}: {e}")

        # 2. PREPARE AGENT INPUT
        # Convert Pydantic model to dict, but override the attachments with just filenames
        agent_input = {
            "patient_message": payload.patient_message,
            "patient_attachment": filenames_for_agent, # Agent gets ["lab.png"], NOT the bytes
            "patient_form": payload.patient_form
        }

        # 3. CALL AGENT
        response_data = await chat_agent.pre_consulte_agent(
            user_request=agent_input,
            patient_id=payload.patient_id
        )

        return ChatResponse(
            patient_id=payload.patient_id,
            nurse_response=response_data,
            status="success"
        )

    except FileNotFoundError:
        logger.error(f"Patient data not found for ID: {payload.patient_id}")
        raise HTTPException(status_code=404, detail="Patient data not found.")
    
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

@app.get("/patients")
async def get_patients():
    """
    Retrieves a list of all patient IDs.
    """
    patient_pool = []
    try:
        file_list = chat_agent.gcs.list_files("patient_data")
        for p in file_list:
            patient_id = p.replace('/',"")  # Extract patient ID from path
            basic_data = json.loads(chat_agent.gcs.read_file_as_string(f"patient_data/{patient_id}/basic_info.json"))
            patient_pool.append(basic_data)
        return patient_pool
    except Exception as e:
        logger.error(f"Error fetching patient list: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve patient list")

@app.post("/chat/{patient_id}/reset")
async def reset_chat_history(patient_id: str):
    """
    Resets the chat history for a specific patient to the default initial greeting.
    """
    try:
        # Define the default starting state
        default_chat_state = {
            "conversation": [
                {
                    'sender': 'admin',
                    'message': 'Hello, this is Linda the Hepatology Clinic admin desk. How can I help you today?'
                }
            ]
        }
        
        # Define the path in GCS
        file_path = f"patient_data/{patient_id}/pre_consultation_chat.json"
        
        # Convert to JSON string
        json_content = json.dumps(default_chat_state, indent=4)
        
        # Overwrite the file in GCS using the agent's bucket manager
        chat_agent.gcs.create_file_from_string(
            json_content, 
            file_path, 
            content_type="application/json"
        )
        
        logger.info(f"Chat history reset for patient: {patient_id}")
        
        return {
            "status": "success", 
            "message": "Chat history has been reset.",
            "current_state": default_chat_state
        }

    except Exception as e:
        logger.error(f"Error resetting chat for {patient_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to reset chat: {str(e)}")


@app.get("/process/{patient_id}/preconsult")
async def process_pre_consult(patient_id: str):
    """
    Resets the chat history for a specific patient to the default initial greeting.
    """
    try:
        data_process = my_agents.RawDataProcessing()
        await data_process.process_raw_data(patient_id)
        
        return {
            "status": "success", 
            "message": "Chat history has been reset."
            }

    except Exception as e:
        logger.error(f"Error processing patient for {patient_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process patient: {str(e)}")

@app.get("/image/{patient_id}/{file_path}")
async def get_image(patient_id:str, file_path: str):

    try:
        byte_data = chat_agent.gcs.read_file_as_bytes(f"patient_data/{patient_id}/raw_data/{file_path}")
        
        return {
            "file": file_path, 
            "data": byte_data
            }

    except Exception as e:
        logger.error(f"Error getting image for {patient_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get image: {str(e)}")


# --- Run Block ---
if __name__ == "__main__":
    # Run with: python server.py
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)