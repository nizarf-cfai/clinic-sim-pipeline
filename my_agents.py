import os
import json
import base64
import uuid
import asyncio
import logging
from google import genai
from google.genai import types
from fastapi import WebSocket
from PIL import Image
from io import BytesIO
import bucket_ops

from dotenv import load_dotenv
load_dotenv()
# Configure logging
logger = logging.getLogger("medforce-backend")


MODEL = "gemini-2.5-flash-lite"
IMAGE_MODEL = "gemini-3-pro-image-preview"
IMAGE_MODEL2 = "gemini-2.5-flash-image"

class BaseLogicAgent:
    def __init__(self):
        self.client = genai.Client(
            vertexai=True, 
            project=os.getenv("PROJECT_ID"), 
            location=os.getenv("PROJECT_LOCATION", "us-central1")
            )



class PatientManager(BaseLogicAgent):
    def __init__(self, args: dict = None):
        super().__init__()
        # Additional initialization if needed
        self.args = args
        if  self.args.get("patient_id"):
            os.makedirs(f"output/{self.args['patient_id']}", exist_ok=True)
            self.output_dir = f"output/{self.args['patient_id']}"

        self.bucket_path = f"patient_data/{self.args.get('patient_id')}"

        self.gcs = bucket_ops.GCSBucketManager(bucket_name="clinic_sim")

        self.patient_profile = ""
        self.patient_system_prompt = ""
        self.encounters = []
        self.labs = []



    async def generate_patient_profile(self, input_criteria = None):
        if not input_criteria: 
            input_criteria = self.args
        
        with open("system_prompts/patient_generator.md", "r", encoding="utf-8") as f: 
            system_instruction = f.read()

        prompt_content = f"Please generate a patient profile based on these parameters:\n{json.dumps(input_criteria, indent=2)}"

        response = await self.client.aio.models.generate_content(
            model=MODEL, 
            contents=prompt_content,
            config=types.GenerateContentConfig(
                response_mime_type="text/plain", # Returns raw text/markdown
                system_instruction=system_instruction, 
                temperature=0.7 # Higher temperature for better storytelling/narrative
            )
        )
        
        # Return the generated text directly
        self.patient_profile = response.text
        with open(f"{self.output_dir}/patient_profile.txt", "w", encoding="utf-8") as f:
            f.write(self.patient_profile)
            
        return response.text
    
    async def generate_system_prompt(self, patient_profile_text):
        if not patient_profile_text: 
            patient_profile_text = self.patient_profile


        with open("system_prompts/system_prompt_generator.md", "r", encoding="utf-8") as f: 
            system_instruction = f.read()

        prompt_content = (
            f"SOURCE PATIENT PROFILE:\n"
            f"{patient_profile_text}\n\n"
            f"TASK:\n"
            f"Write the SYSTEM PROMPT for this patient."
        )

        response = await self.client.aio.models.generate_content(
            model=MODEL, 
            contents=prompt_content,
            config=types.GenerateContentConfig(
                response_mime_type="text/plain", 
                system_instruction=system_instruction, 
                temperature=0.5 # Lower temp to stick strictly to the facts provided in the profile
            )
        )
        self.patient_system_prompt = response.text
        with open(f"{self.output_dir}/system_prompt.txt", "w", encoding="utf-8") as f:
            f.write(self.patient_system_prompt)
        return response.text

    async def generate_encounters_narrative(self, patient_profile_text, criteria):

        with open("system_prompts/encounter_narrative.md", "r", encoding="utf-8") as f: 
            system_instruction = f.read()

        if not patient_profile_text: 
            return "Error: No patient profile provided."
        
        try:
            # We combine the profile with the specific instructions for this run
            prompt_content = (
                f"### PATIENT MASTER PROFILE ###\n"
                f"{patient_profile_text}\n\n"
                f"### ENCOUNTER GENERATION CRITERIA ###\n"
                f"{json.dumps(criteria, indent=2)}\n\n"
                f"### TASK ###\n"
                f"Generate the detailed clinical narrative for these encounters. "
                f"Ensure the timeline makes sense (dates relative to Today). "
                f"For each encounter, provide full SOAP notes (Subjective, Objective, Assessment, Plan)."
            )

            response = await self.client.aio.models.generate_content(
                model=MODEL, 
                contents=prompt_content,
                config=types.GenerateContentConfig(
                    response_mime_type="text/plain", 
                    system_instruction=system_instruction, 
                    temperature=0.5 # Balanced creativity and logic
                )
            )
            
            return response.text
            
        except Exception as e:
            print(f"Error in generate_encounter_story: {e}") 
            return f"Error: {str(e)}"


    async def generate_encounters(self, patient_profile_text):

        if not patient_profile_text: 
            patient_profile_text = self.patient_profile
        
        with open("system_prompts/encounter_generator.md", "r", encoding="utf-8") as f: 
            system_instruction = f.read()
        with open("response_schema/encounter.json", "r", encoding="utf-8") as f:
            response_schema = json.load(f)

        encounter_narrative = await self.generate_encounters_narrative(patient_profile_text, self.args)

        self.gcs.create_file_from_string(encounter_narrative, f"{self.bucket_path}/encounter_narrative.txt", content_type="text/plain")

        try:
            # We explicitly ask for a list of encounters based on the profile
            prompt = f"Patient Profile:\n{patient_profile_text}\n\nEncounter Narrative:\n{encounter_narrative}\nTask: Generate the past medical encounters timeline for this patient as a JSON array."
            
            response = await self.client.aio.models.generate_content(
                model=MODEL, 
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_schema=response_schema, 
                    response_mime_type="application/json", 
                    system_instruction=system_instruction,
                    temperature=0.4 # Keep history consistent and logical, less random
                )
            )
            
            res = json.loads(response.text)
            self.encounters = res
            with open(f"{self.output_dir}/encounters.json", "w", encoding="utf-8") as f:
                json.dump(self.encounters, f, indent=4)
            return res
        except Exception as e:
            print(f"Error in generate_encounters: {e}") 
            return []

    async def generate_labs(self, patient_profile_text, encounters):
        if not patient_profile_text and not encounters: 
            patient_profile_text = self.patient_profile
            encounters = self.encounters

        with open("system_prompts/lab_generator.md", "r", encoding="utf-8") as f: 
            system_instruction = f.read()
        with open("response_schema/labs.json", "r", encoding="utf-8") as f:
            response_schema = json.load(f)

        try:
            # We prompt the model to focus on the 'Clinical Reasoning' section of the profile
            prompt = (
                f"PATIENT PROFILE:\n{patient_profile_text}\n\n"
                f"PATIENT ENCOUNTRES:\n{json.dumps(encounters)}\n\n"
                f"TASK: Generate a full lab report (CBC and Chemistry) for this patient. "
                f"Ensure the abnormal values align with the diagnosis described above."
            )
            
            response = await self.client.aio.models.generate_content(
                model=MODEL, 
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", 
                    response_schema=response_schema, 
                    system_instruction=system_instruction, 
                    temperature=0.3 # Low temperature is crucial for math/range consistency
                )
            )
            
            res = json.loads(response.text)

            self.labs = res
            with open(f"{self.output_dir}/labs.json", "w", encoding="utf-8") as f:
                json.dump(self.labs, f, indent=4)
            return res
        except Exception as e:
            print(f"Error in generate_labs: {e}") 
            return []

    def group_labs_by_date(self,labs_data):

        grouped = {}

        for item in labs_data:
            # Extract static metadata for this biomarker
            biomarker_name = item.get("biomarker")
            unit = item.get("unit")
            ref_min = item.get("referenceRange", {}).get("min")
            ref_max = item.get("referenceRange", {}).get("max")

            # Iterate through the time-series values
            for measurement in item.get("values", []):
                timestamp = measurement.get("t")
                value = measurement.get("value")

                # Initialize the date group if it doesn't exist
                if timestamp not in grouped:
                    grouped[timestamp] = {
                        "date_time": timestamp,
                        "labs": []
                    }

                # Determine Flag (High/Low/Normal)
                flag = "NORMAL"
                if ref_min is not None and ref_max is not None:
                    if value < ref_min:
                        flag = "LOW"
                    elif value > ref_max:
                        flag = "HIGH"

                # Add this specific result to the group
                grouped[timestamp]["labs"].append({
                    "biomarker": biomarker_name,
                    "value": value,
                    "unit": unit,
                    "reference_range": f"{ref_min} - {ref_max}",
                    "flag": flag
                })

        # Convert dictionary to a list and sort by date (Newest last)
        # ISO 8601 dates (YYYY-MM-DD) sort correctly as strings
        sorted_results = sorted(list(grouped.values()), key=lambda x: x['date_time'])
        
        return sorted_results

    async def imaging_doc_parser(self, encounter_object):
        with open("system_prompts/imaging_report_generator.md", "r", encoding="utf-8") as f: 
                system_instruction = f.read()

        if not encounter_object: 
            return None
        
        try:
            # Extract key context to help the LLM write an accurate report
            enc = encounter_object.get('encounter', encounter_object)
            pat = encounter_object.get('patient', {})
            
            # Try to find what imaging was ordered
            plan_investigations = enc.get('plan', {}).get('investigations', {})
            # Fallback logic if specific imaging key isn't found
            ordered_test = str(plan_investigations) if plan_investigations else "Chest X-Ray (Assumed)"
            
            diagnosis = enc.get('assessment', {}).get('impression', 'Under Investigation')
            symptoms = enc.get('chief_complaint', 'N/A')
            
            context_summary = {
                "patient": pat,
                "ordered_exam": ordered_test,
                "diagnosis_to_support": diagnosis,
                "indication": symptoms
            }

            prompt_content = (
                f"### CLINICAL CONTEXT ###\n"
                f"{json.dumps(context_summary, indent=2)}\n\n"
                f"### TASK ###\n"
                f"Write the full text of the Radiology Report for the exam listed above. "
                f"The 'Findings' must support the diagnosis of '{diagnosis}'. "
                f"If the diagnosis is serious, the findings must be abnormal. "
                f"Format it as a clean, professional medical document."
            )

            response = await self.client.aio.models.generate_content(
                model=MODEL, 
                contents=prompt_content,
                config=types.GenerateContentConfig(
                    response_mime_type="text/plain", 
                    system_instruction=system_instruction, 
                    temperature=0.4 # Low temp for professional medical tone
                )
            )
            
            return response.text
            
        except Exception as e:
            print(f"Error in generate_report_content: {e}") 
            return "Error generating imaging report."


    async def lab_doc_parser(self, lab_encounter_json,patient_name):
        with open("system_prompts/lab_parser.md", "r", encoding="utf-8") as f: 
            system_instruction = f.read()

        if not lab_encounter_json: 
            return "Error: Empty Data"
        
        try:
            # We add the patient name to the prompt context so the header is complete
            input_context = {
                "patient_name": patient_name,
                "lab_data": lab_encounter_json
            }
            
            prompt_content = (
                f"RAW LAB DATA:\n{json.dumps(input_context, indent=2)}\n\n"
                f"TASK: Format this into a clean, fixed-width Laboratory Result Report."
            )

            response = await self.client.aio.models.generate_content(
                model=MODEL, 
                contents=prompt_content,
                config=types.GenerateContentConfig(
                    response_mime_type="text/plain", 
                    system_instruction=system_instruction, 
                    temperature=0.1 # Very low temperature to ensure numbers are copied exactly
                )
            )
            
            return response.text
            
        except Exception as e:
            print(f"Error in generate_lab_content: {e}") 
            return "Error parsing lab document."


    async def encounter_doc_parser(self, encounter_object):
        with open("system_prompts/encounter_parser.md", "r", encoding="utf-8") as f: 
            system_instruction = f.read()

        if not encounter_object: 
            return "Error: Empty Data"
        
        try:
            # We pass the raw JSON to the model
            prompt_content = f"Raw Encounter Data:\n{json.dumps(encounter_object, indent=2)}\n\nTask: Format this into a printable Medical Summary Report text."

            response = await self.client.aio.models.generate_content(
                model=MODEL, 
                contents=prompt_content,
                config=types.GenerateContentConfig(
                    response_mime_type="text/plain", # We want formatted text, not JSON
                    system_instruction=system_instruction, 
                    temperature=0.3 # Low temperature for consistent formatting
                )
            )
            
            return response.text
            
        except Exception as e:
            print(f"Error in generate_document_content: {e}") 
            return "Error parsing document."

    async def generate_encounter_img(self, document_text, output_filename="encounter_report.png"):

        if not document_text:
            print("Error: No document text provided.")
            return None
        


        # Construct a prompt that asks the model to render the specific text
        # Note: Generative models may summarize text visually; they are not PDF printers.
        # We emphasize "legible text" to get the best result.
        prompt = (
            f"A realistic, high-resolution, top-down close-up photo of a printed medical summary report "
            f"The paper is white and clean. Potrait A4 size. "
            f"The document is clearly formatted with headers. "
            f"The visible text content on the page corresponds to:\n\n"
            f"{document_text}\n\n"
            f"Ensure the Hospital Header and Patient Name are prominent and legible. Generate the fictional signature of the doctor at the bottom."
        )

        models_to_try = [IMAGE_MODEL, IMAGE_MODEL2]

        for model_name in models_to_try:
            try:
                print(f"Generating image for radiology report using {model_name}...")
                
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        image_config=types.ImageConfig(
                            aspect_ratio="9:16",
                        ),
                    )
                )

                # Check response parts for image data
                for part in response.parts:
                    if part.inline_data is not None:
                        # SUCCESS: Save and return immediately
                        image = part.as_image()
                        image.save(output_filename)
                        print(f"Success: Image generated with {model_name} and saved to {output_filename}")
                        return output_filename
                    elif part.text is not None:
                        # Warning: Model returned text (likely a refusal or safety filter)
                        print(f"Warning: {model_name} returned text instead of image: {part.text}")

                print(f"{model_name} failed to produce an image. Retrying with next model...")

            except Exception as e:
                print(f"Error encountered with {model_name}: {e}. Retrying with next model...")
                continue # Explicitly continue to the next model in the list

        # If loop finishes and no image was returned
        print("Error: All image generation models failed.")
        return None


    async def generate_lab_img(self, lab_object, patient_name, output_filename="lab_report.png"):

        if not lab_object:
            print("Error: No lab object provided.")
            return None
        
        # Generate the formatted text table first
        document_text = await self.lab_doc_parser(lab_object, patient_name)

        # Construct a prompt specifically for tabular lab data
        prompt = (
            f"A realistic, high-resolution, top-down close-up photo of a printed Laboratory Result Report. "
            f"The paper is white and clean. Portrait A4 size. "
            f"The document features a clearly structured text-based table. "
            f"The visible text content on the page corresponds to:\n\n"
            f"{document_text}\n\n"
            f"Ensure the columns (Test Name, Result, Flag) are visually aligned like a real monospaced medical printout. "
            f"The 'HIGH' or 'LOW' flags should be clearly distinct. "
            f"Include a 'Verified by Pathologist' signature or stamp at the bottom."
        )

        models_to_try = [IMAGE_MODEL, IMAGE_MODEL2]

        for model_name in models_to_try:
            try:
                print(f"Generating image for lab report using {model_name}...")
                
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        image_config=types.ImageConfig(
                            aspect_ratio="9:16",
                        ),
                    )
                )

                # Check response parts for image data
                for part in response.parts:
                    if part.inline_data is not None:
                        # SUCCESS: Save and return immediately
                        image = part.as_image()
                        image.save(output_filename)
                        print(f"Success: Image generated with {model_name} and saved to {output_filename}")
                        return output_filename
                    elif part.text is not None:
                        # Warning: Model returned text (likely a refusal or safety filter)
                        print(f"Warning: {model_name} returned text instead of image: {part.text}")

                print(f"{model_name} failed to produce an image. Retrying with next model...")

            except Exception as e:
                print(f"Error encountered with {model_name}: {e}. Retrying with next model...")
                continue # Explicitly continue to the next model in the list

        # If loop finishes and no image was returned
        print("Error: All image generation models failed.")
        return None

        


    async def generate_imaging_report_img(self, imaging_doc_text, output_filename="radiology_report.png"):

        if not imaging_doc_text:
            print("Error: No imaging document text provided.")
            return None

        with open(f"{self.output_dir}/imaging_doc_text.txt", "w", encoding="utf-8") as f:
            f.write(imaging_doc_text)

        # CLEANING STEP: 
        # The previous agent adds a hidden "[[IMAGE_PROMPT...]]" at the bottom.
        # We must strip that out because we don't want it printed on the fake paper.
        clean_document_text = imaging_doc_text

        # if "[[" in imaging_doc_text:
        #     clean_document_text = imaging_doc_text.split("[[")[0].strip()
        # else:
        #     clean_document_text = imaging_doc_text

        # Construct a prompt specifically for a text-heavy radiology document
        prompt = (
            f"A realistic, high-resolution, top-down close-up photo of a printed Radiology/Imaging Report. "
            f"The paper is white and clean. Portrait A4 size. "
            f"The document features a formal header 'DEPARTMENT OF RADIOLOGY'. "
            f"The visible text content on the page corresponds to:\n\n"
            f"{clean_document_text}\n\n"
            f"Ensure the text is legible, appearing like a standard laser-printed medical record. "
            f"The 'FINDINGS' and 'IMPRESSION' sections should be clearly distinct. "
            f"Include a signature at the bottom."
        )

        models_to_try = [IMAGE_MODEL, IMAGE_MODEL2]

        for model_name in models_to_try:
            try:
                print(f"Generating image for radiology report using {model_name}...")
                
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        image_config=types.ImageConfig(
                            aspect_ratio="9:16",
                        ),
                    )
                )

                # Check response parts for image data
                for part in response.parts:
                    if part.inline_data is not None:
                        # SUCCESS: Save and return immediately
                        image = part.as_image()
                        image.save(output_filename)
                        print(f"Success: Image generated with {model_name} and saved to {output_filename}")
                        return output_filename
                    elif part.text is not None:
                        # Warning: Model returned text (likely a refusal or safety filter)
                        print(f"Warning: {model_name} returned text instead of image: {part.text}")

                print(f"{model_name} failed to produce an image. Retrying with next model...")

            except Exception as e:
                print(f"Error encountered with {model_name}: {e}. Retrying with next model...")
                continue # Explicitly continue to the next model in the list

        # If loop finishes and no image was returned
        print("Error: All image generation models failed.")
        return None


    async def generate_pre_consultation_chat(self):
        with open("system_prompts/pre_consult_chat_generator.md", "r", encoding="utf-8") as f: 
            system_instruction = f.read()
        with open("response_schema/pre_consult_chat_generator.json", "r", encoding="utf-8") as f:
            response_schema = json.load(f)

        patient_profile = self.gcs.read_file_as_string(f"{self.bucket_path}/patient_profile.txt")
        file_inventory = json.loads(self.gcs.read_file_as_string(f"{self.bucket_path}/raw_data.json"))
        try:
            # 1. Summarize the Context for the LLM
            # We explicitly list the filenames so the LLM knows what to "upload"
            context = {
                "available_files": file_inventory,
                "appointment_context": "Specialist Consultation Booking",
                "clinic_name": "General Hepatology Clinic"
            }

            prompt_content = (
                f"### PATIENT PROFILE (PERSONA) ###\n{patient_profile}\n\n"
                f"### MEDICAL HISTORY SUMMARY ###\n(Refer to the current encounter in the profile for symptoms)\n\n"
                f"### FILE INVENTORY (Documents the patient possesses) ###\n{json.dumps(context, indent=2)}\n\n"
                f"### TASK ###\n"
                f"Generate a WhatsApp-style chat transcript between 'admin' (Nurse/Receptionist) and 'patient'.\n"
                f"The Admin must verify identity, ask about symptoms, and request the documents listed in the Inventory.\n"
                f"The Patient must answer according to their Persona (e.g., if anxious, sound anxious) and upload the files when asked."
            )

            response = await self.client.aio.models.generate_content(
                model=MODEL, 
                contents=prompt_content,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", 
                    response_schema=response_schema, 
                    system_instruction=system_instruction, 
                    temperature=0.6 # Moderate temp for natural conversation flow
                )
            )
            
            res = json.loads(response.text)
            self.gcs.create_file_from_string(json.dumps(res, indent=4), f"{self.bucket_path}/pre_consultation_chat.json", content_type="application/json")
            return res
        except Exception as e:
            print(f"Error in generate_transcript: {e}") 
            return {"conversation": []}
        


    async def generate_ground_truth(self):
        print("Generating Ground Truth Data...")
        print("Generating Patient Profile...")
        patient_profile = await self.generate_patient_profile()
        self.gcs.create_file_from_string(patient_profile, f"{self.bucket_path}/patient_profile.txt", content_type="text/plain")

        print("Generating System Prompt...")
        patient_system_prompt = await self.generate_system_prompt(patient_profile)
        self.gcs.create_file_from_string(patient_system_prompt, f"{self.bucket_path}/system_prompt.txt", content_type="text/plain")

        print("Generating Encounters...")
        encounters = await self.generate_encounters(patient_profile)
        self.gcs.create_file_from_string(json.dumps(encounters, indent=4), f"{self.bucket_path}/encounters.json", content_type="application/json")

        print("Generating Labs...")
        labs = await self.generate_labs(patient_profile, encounters)
        self.gcs.create_file_from_string(json.dumps(labs, indent=4), f"{self.bucket_path}/labs.json", content_type="application/json")

        grouped_labs = self.group_labs_by_date(labs)

        encounter_docs = []
        for i, encounter in enumerate(encounters):
            encounter_doc = await self.encounter_doc_parser(encounter)
            encounter_docs.append({
                "file" : f"encounter_report_{i}_{encounter['encounter']['meta']['date_time'].split('T')[0]}.txt",
                "date_time": encounter['encounter']['meta']['date_time'],
                "encounter_report_text": encounter_doc
            })
            # Save each individual encounter report text file
            self.gcs.create_file_from_string(
                encounter_doc, 
                f"{self.bucket_path}/encounter_report_{i}_{encounter['encounter']['meta']['date_time'].split('T')[0]}.txt", 
                content_type="text/plain"
            )


        lab_docs = []
        for i, lab_entry in enumerate(grouped_labs):
            lab_doc = await self.lab_doc_parser(lab_entry, encounters[0].get("patient",{}).get("name"))
            lab_docs.append({
                "file" : f"lab_report_{i}_{lab_entry['date_time'].split('T')[0]}.txt",
                "image_file" : f"lab_report_{i}_{lab_entry['date_time'].split('T')[0]}.txt",
                "date_time": lab_entry["date_time"],
                "lab_report_text": lab_doc
            })
            # Save each individual lab report text file
            self.gcs.create_file_from_string(
                lab_doc, 
                f"{self.bucket_path}/lab_report_{i}_{lab_entry['date_time'].split('T')[0]}.txt", 
                content_type="text/plain"
            )

        imaging_docs = []
        for i, encounter in enumerate(encounters):
            if encounter.get("encounter",{}).get("plan",{}).get("investigations",{}).get("imaging"):
                imaging_doc = await self.imaging_doc_parser(encounter)
                imaging_docs.append({
                    "file" : f"imaging_report_{i}_{encounter['encounter']['meta']['date_time'].split('T')[0]}.txt",
                    "date_time": encounter['encounter']['meta']['date_time'],
                    "imaging_report_text": imaging_doc
                })
                # Save each individual imaging report text file
                self.gcs.create_file_from_string(
                    imaging_doc, 
                    f"{self.bucket_path}/imaging_report_{i}_{encounter['encounter']['meta']['date_time'].split('T')[0]}.txt", 
                    content_type="text/plain"
                )

        raw_data = {
            "encounter_reports": encounter_docs,
            "lab_reports": lab_docs,
            "imaging_reports": imaging_docs
        }
        self.gcs.create_file_from_string(json.dumps(raw_data, indent=4), f"{self.bucket_path}/raw_data.json", content_type="application/json")

        ### GENERATE IMAGES
        print("Generating Encounter Images...")
        for enc_doc in encounter_docs:
            img_file = await self.generate_encounter_img(enc_doc["encounter_report_text"], output_filename=f"{self.output_dir}/{enc_doc['file'].replace('.txt','.png')}")
            if img_file:
                # Upload to GCS
                with open(img_file, "rb") as f:
                    self.gcs.create_file_from_string(
                        f.read(), 
                        f"{self.bucket_path}/{enc_doc['file'].replace('.txt','.png')}", 
                        content_type="image/png"
                    )
        print("Generating Lab Images...")
        for lab_doc in lab_docs:
            img_file = await self.generate_lab_img(
                lab_entry, 
                encounters[0].get("patient",{}).get("name"), 
                output_filename=f"{self.output_dir}/{lab_doc['file'].replace('.txt','.png')}"
            )
            if img_file:
                # Upload to GCS
                with open(img_file, "rb") as f:
                    self.gcs.create_file_from_string(
                        f.read(), 
                        f"{self.bucket_path}/{lab_doc['file'].replace('.txt','.png')}", 
                        content_type="image/png"
                    )
        print("Generating Imaging Report Images...")
        for img_doc in imaging_docs:
            img_file = await self.generate_imaging_report_img(
                img_doc["imaging_report_text"], 
                output_filename=f"{self.output_dir}/{img_doc['file'].replace('.txt','.png')}"
            )
            if img_file:
                # Upload to GCS
                with open(img_file, "rb") as f:
                    self.gcs.create_file_from_string(
                        f.read(), 
                        f"{self.bucket_path}/{img_doc['file'].replace('.txt','.png')}", 
                        content_type="image/png"
                    )


class PreConsulteAgent(BaseLogicAgent):
    def __init__(self):
        super().__init__()  
        self.gcs = bucket_ops.GCSBucketManager(bucket_name="clinic_sim")

    async def pre_consulte_agent(self,current_user_message, patient_id:str):

        with open("system_prompts/live_admin_agent.md", "r", encoding="utf-8") as f: 
                system_instruction = f.read()

        # 1. Format the current input to append to history for context
        # If the user sent an attachment, we explicitly describe it in the prompt
        pre_consultation_chat = json.loads(self.gcs.read_file_as_string(f"patient_data/{patient_id}/pre_consultation_chat.json"))


        try:
            # 2. Construct the Context
            # We serialize the history so the LLM knows what has already been asked/answered.
            prompt_content = (
                f"### CONVERSATION HISTORY (JSON) ###\n"
                f"{json.dumps(pre_consultation_chat, indent=2)}\n\n"
                f"### LATEST USER TEXT ###\n"
                f"{current_user_message}\n\n"
                f"### TASK ###\n"
                f"Analyze the history. Check the last message for 'attachment' keys. "
                f"Determine the next step in the Protocol Checklist. "
                f"Generate the response."
            )

            response = await self.client.aio.models.generate_content(
                model=MODEL, 
                contents=prompt_content,
                config=types.GenerateContentConfig(
                    response_mime_type="text/plain", 
                    system_instruction=system_instruction, 
                    temperature=0.3 # Low temp to stick strictly to the protocol
                )
            )
            
            pre_consultation_chat['conversation'].append({
                'sender': 'patient',
                'message': current_user_message
            })

            pre_consultation_chat['conversation'].append({
                'sender': 'admin',
                'message': response.text.strip()
            })

            self.gcs.create_file_from_string(json.dumps(pre_consultation_chat, indent=4), f"patient_data/{patient_id}/pre_consultation_chat.json", content_type="application/json")


            return response.text.strip()
            
        except Exception as e:
            print(f"Error in generate_reply: {e}") 
            return "I apologize, I'm having trouble connecting to the system. Could you please repeat that?"