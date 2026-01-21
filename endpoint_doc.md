Here is the Markdown documentation for your API.

# MedForce Hepatology Chat API Documentation

**Base URL:** `https://clinic-sim-pipeline-481780815788.europe-west1.run.app`

This API handles the live simulation of a Hepatology Clinic Admin (Nurse Linda). It manages patient conversations, state processing via AI agents, and conversation history retrieval from Google Cloud Storage.

---

## Endpoints

### 1. Send Message to Agent
Process a patient message, attachment, or form submission through the AI logic and get the Admin's response.

*   **URL:** `/chat`
*   **Method:** `POST`
*   **Content-Type:** `application/json`

#### Request Body (`ChatRequest`)
| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `patient_id` | string | Yes | The unique identifier for the patient (e.g., "P0001"). |
| `patient_message` | string | Yes | The text message from the patient. |
| `patient_attachment` | list[str] | No | A list of filenames if the user is simulating a file upload. |
| `patient_form` | dict | No | A JSON object containing the filled intake form data (used when responding to a `SEND_FORM` action). |

**Example Request (Standard Text):**
```json
{
  "patient_id": "P0001",
  "patient_message": "Hi, I need to book an appointment."
}
```

**Example Request (Form Submission):**
```json
{
  "patient_id": "P0001",
  "patient_message": "I have filled out the form.",
  "patient_form": {
      "name": "John Doe",
      "dob": "1980-01-01",
      "complaint": "Jaundice"
  }
}
```

#### Response (`ChatResponse`)
| Field | Type | Description |
| :--- | :--- | :--- |
| `patient_id` | string | The ID of the patient. |
| `status` | string | Request status (e.g., "success"). |
| `nurse_response` | object | The structured response from the AI Agent. |

**Example Response:**
```json
{
  "patient_id": "P0001",
  "status": "success",
  "nurse_response": {
    "message": "Thank you. Please confirm your details in this form.",
    "action_type": "SEND_FORM",
    "form_request": {
        "name": "",
        "dob": "",
        "contact": {}
    },
    "sender": "admin"
  }
}
```

#### Error Codes
*   **404 Not Found:** Patient data directory does not exist in GCS (Run ground truth generation first).
*   **500 Internal Server Error:** AI processing failure or connectivity issues.

---

### 2. Get Chat History
Retrieve the full conversation history for a specific patient.

*   **URL:** `/chat/{patient_id}`
*   **Method:** `GET`

#### Path Parameters
| Parameter | Type | Description |
| :--- | :--- | :--- |
| `patient_id` | string | The unique identifier for the patient. |

#### Response
Returns the full JSON object stored in the database/storage.

**Example Response:**
```json
{
  "conversation": [
    {
      "sender": "admin",
      "message": "Hello, this is Linda the Hepatology Clinic admin desk. How can I help you today?"
    },
    {
      "sender": "patient",
      "message": "I need an appointment."
    },
    {
      "sender": "admin",
      "message": "Have you booked via the NHS app?",
      "action_type": "TEXT_ONLY"
    }
  ]
}
```

#### Error Codes
*   **404 Not Found:** Chat history file is missing or empty.

---

### 3. Reset Chat History
Wipes the conversation history for a patient and restores the initial greeting. Useful for restarting a simulation scenario.

*   **URL:** `/chat/{patient_id}/reset`
*   **Method:** `POST`

#### Path Parameters
| Parameter | Type | Description |
| :--- | :--- | :--- |
| `patient_id` | string | The unique identifier for the patient. |

#### Response
**Example Response:**
```json
{
  "status": "success",
  "message": "Chat history has been reset.",
  "current_state": {
    "conversation": [
      {
        "sender": "admin",
        "message": "Hello, this is Linda the Hepatology Clinic admin desk. How can I help you today?"
      }
    ]
  }
}
```

---

### 4. Health Check
Check if the server is running.

*   **URL:** `/`
*   **Method:** `GET`

#### Response
```json
{
  "status": "MedForce Server is Running"
}
```