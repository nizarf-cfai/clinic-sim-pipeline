import streamlit as st
import requests
import json

# --- CONFIGURATION ---
API_URL = "http://localhost:8000"
DEFAULT_PATIENT_ID = "P0001" 

st.set_page_config(page_title="MedForce Hepatology Chat", layout="wide", page_icon="🏥")

# --- CSS STYLING ---
st.markdown("""
<style>
    .stChatMessage { padding: 1rem; border-radius: 10px; margin-bottom: 10px; }
    .stButton button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "patient_id" not in st.session_state:
    st.session_state.patient_id = DEFAULT_PATIENT_ID
if "last_action" not in st.session_state:
    st.session_state.last_action = None
if "last_response_payload" not in st.session_state:
    st.session_state.last_response_payload = {}

# --- HELPER FUNCTIONS ---

def reset_chat():
    """Resets chat on backend and frontend."""
    try:
        requests.post(f"{API_URL}/chat/{st.session_state.patient_id}/reset")
        st.session_state.messages = []
        st.session_state.last_action = None
        st.session_state.last_response_payload = {}
        # Add initial greeting manually
        st.session_state.messages.append({
            "role": "assistant",
            "content": "Hello, this is Linda the Hepatology Clinic admin desk. How can I help you today?",
            "action_type": "TEXT_ONLY"
        })
        st.rerun()
    except Exception as e:
        st.error(f"Reset failed: {e}")

def send_to_api(message: str, attachments: list = None, form_data: dict = None):
    """Sends user input to the backend API."""
    
    # 1. Add User Message to UI State immediately
    st.session_state.messages.append({"role": "user", "content": message})
    
    payload = {
        "patient_id": st.session_state.patient_id,
        "patient_message": message,
        "patient_attachment": attachments if attachments else [],
        "patient_form": form_data if form_data else {}
    }

    try:
        with st.spinner("Linda is typing..."):
            response = requests.post(f"{API_URL}/chat", json=payload)
            
        if response.status_code == 200:
            data = response.json()
            nurse_resp = data["nurse_response"]
            
            # Extract core fields
            msg_text = nurse_resp.get("message", "")
            action = nurse_resp.get("action_type", "TEXT_ONLY")
            
            # Update Session State
            st.session_state.messages.append({
                "role": "assistant", 
                "content": msg_text,
                "payload": nurse_resp # Store full object for rendering forms/slots
            })
            st.session_state.last_action = action
            st.session_state.last_response_payload = nurse_resp
            
        else:
            st.error(f"API Error: {response.text}")

    except Exception as e:
        st.error(f"Connection Error: {e}")

# --- SIDEBAR ---
with st.sidebar:
    st.title("🏥 MedForce")
    st.session_state.patient_id = st.text_input("Patient ID", value=st.session_state.patient_id)
    
    if st.button("Reset Chat", type="primary"):
        reset_chat()

    st.markdown("---")
    with st.expander("Debug Info"):
        st.write(f"Action: `{st.session_state.last_action}`")
        st.json(st.session_state.last_response_payload)

# --- MAIN CHAT UI ---
st.header("Hepatology Clinic Live Chat")

# 1. Render Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        # Confirmation Card UI
        if msg.get("payload") and msg["payload"].get("action_type") == "CONFIRM_APPOINTMENT":
            appt = msg["payload"].get("confirmed_appointment", {})
            st.success(f"✅ **Appointment Confirmed**")
            sch = appt.get("schedule", {})
            c1, c2 = st.columns(2)
            c1.write(f"**Date:** {sch.get('date')}")
            c2.write(f"**Time:** {sch.get('time')}")
            st.write(f"**Provider:** {sch.get('provider')}")
            st.caption(f"Location: {sch.get('location')}")

# 2. Dynamic Action Handling (Forms, Slots)
last_payload = st.session_state.last_response_payload
current_action = st.session_state.last_action

# --- SCENARIO: FORM FILLING (Fixed for Nested Structure) ---
if current_action == "SEND_FORM":
    with st.chat_message("assistant"):
        st.info("📋 **Patient Intake Form**")
        
        # Get the structure directly from form_request based on your JSON example
        form_data = last_payload.get("form_request", {})

        with st.form("patient_intake_form"):
            st.markdown("#### 👤 Personal Information")
            col1, col2 = st.columns(2)
            with col1:
                f_name = st.text_input("Full Name", value=form_data.get("name", ""))
                f_first = st.text_input("First Name", value=form_data.get("firstName", ""))
                f_dob = st.text_input("Date of Birth (YYYY-MM-DD)", value=form_data.get("dob", ""))
                f_occupation = st.text_input("Occupation", value=form_data.get("occupation", ""))
            with col2:
                f_gender = st.text_input("Gender", value=form_data.get("gender", ""))
                f_last = st.text_input("Last Name", value=form_data.get("lastName", ""))
                f_age = st.text_input("Age", value=str(form_data.get("age") or ""))
                f_marital = st.text_input("Marital Status", value=form_data.get("maritalStatus", ""))

            st.markdown("---")
            st.markdown("#### 📞 Contact Details")
            
            # Access nested contact dictionary
            c_data = form_data.get("contact", {})
            
            c1, c2 = st.columns(2)
            c_phone = c1.text_input("Phone Number", value=c_data.get("phone", ""))
            c_email = c2.text_input("Email Address", value=c_data.get("email", ""))
            
            # Nested Address
            st.markdown("**Home Address**")
            addr_data = c_data.get("address", {})
            a_street = st.text_input("Street Address", value=addr_data.get("street", ""))
            ac1, ac2, ac3 = st.columns(3)
            a_city = ac1.text_input("City", value=addr_data.get("city", ""))
            a_state = ac2.text_input("State", value=addr_data.get("state", ""))
            a_zip = ac3.text_input("Zip Code", value=addr_data.get("zipCode", ""))

            # Nested Emergency Contact
            st.markdown("**Emergency Contact**")
            e_data = c_data.get("emergency", {})
            ec1, ec2, ec3 = st.columns(3)
            e_name = ec1.text_input("Name", value=e_data.get("name", ""))
            e_rel = ec2.text_input("Relation", value=e_data.get("relation", ""))
            e_phone = ec3.text_input("Phone", value=e_data.get("phone", ""))

            st.markdown("---")
            st.markdown("#### 🏥 Medical Details")
            f_complaint = st.text_area("Chief Complaint", value=form_data.get("complaint", ""), help="Why are you visiting today?")
            
            # Handle Lists (Medical History & Allergies) -> Convert to comma separated string for UI
            hist_raw = form_data.get("medical_history", [])
            hist_str = ", ".join(hist_raw) if isinstance(hist_raw, list) else str(hist_raw)
            f_history = st.text_area("Medical History (Separate by comma)", value=hist_str)

            all_raw = form_data.get("allergies", [])
            all_str = ", ".join(all_raw) if isinstance(all_raw, list) else str(all_raw)
            f_allergies = st.text_area("Allergies (Separate by comma)", value=all_str)

            # Submit Button
            submitted = st.form_submit_button("✅ Submit Intake Form", type="primary")

            if submitted:
                # Reconstruct the Nested JSON to send back to backend
                submission = {
                    "name": f_name, "firstName": f_first, "lastName": f_last,
                    "dob": f_dob, "age": f_age, "gender": f_gender,
                    "occupation": f_occupation, "maritalStatus": f_marital,
                    "contact": {
                        "phone": c_phone, "email": c_email,
                        "address": {
                            "street": a_street, "city": a_city, "state": a_state, "zipCode": a_zip
                        },
                        "emergency": {
                            "name": e_name, "relation": e_rel, "phone": e_phone
                        }
                    },
                    "complaint": f_complaint,
                    # Convert comma string back to list
                    "medical_history": [x.strip() for x in f_history.split(",") if x.strip()],
                    "allergies": [x.strip() for x in f_allergies.split(",") if x.strip()]
                }
                
                send_to_api("I have completed the intake form.", form_data=submission)
                st.rerun()

# --- SCENARIO: SLOT PICKING ---
elif current_action == "OFFER_SLOTS":
    with st.chat_message("assistant"):
        st.info("📅 **Available Appointments**")
        st.write("Please select a time slot for Dr. Gupta:")
        
        slots_data = last_payload.get("available_slots", {})
        slots = slots_data.get("slots", [])
        
        # Render cards for slots
        cols = st.columns(3)
        for idx, slot in enumerate(slots):
            # cycle columns
            col = cols[idx % 3]
            with col:
                with st.container(border=True):
                    st.markdown(f"**{slot['date']}**")
                    st.markdown(f"🕒 {slot['time']}")
                    st.caption(f"{slot['type']}")
                    if st.button("Book", key=f"slot_{slot['slotId']}"):
                        selection_text = f"I will take the slot on {slot['date']} at {slot['time']}."
                        send_to_api(selection_text)
                        st.rerun()

# --- STANDARD INPUT ---
# File Uploader
uploaded_file = st.file_uploader("📎 Attach Document (Optional)", type=["png", "jpg", "pdf"])

if prompt := st.chat_input("Type your message..."):
    attachments = []
    if uploaded_file:
        attachments.append(uploaded_file.name)
        st.toast(f"Attached: {uploaded_file.name}")
    
    send_to_api(prompt, attachments=attachments)
    st.rerun()