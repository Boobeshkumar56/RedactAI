import os
import json
import re
import subprocess
import shlex
import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

"""
This file contains the code for AI-based document analysis.
It integrates with Google's Gemini AI to identify sensitive information in documents.
"""

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# Get API key from environment variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Check if API key exists
if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY environment variable is not set. Please set it in your .env file.")
    # You can uncomment and set a hardcoded key for testing ONLY
    # GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE" 
    print(f"Environment variables: {os.environ.get('PATH')[:20]}...")


def analyze_document_text(text: str, document_type: str = "unknown") -> List[Dict[str, Any]]:
    """
    Analyze document text to identify sensitive information using Gemini AI.
    
    Args:
        text: The extracted text from the document
        document_type: The type of document if known
        
    Returns:
        A list of identified sensitive fields with their categories
    """
    # Print the extracted text for debugging
    print("\n========== EXTRACTED TEXT ==========")
    print(text[:500] + "..." if len(text) > 500 else text)
    print("====================================\n")
    
    # Check if API key is available
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY is not set in .env file. Falling back to regex-based analysis.")
        return analyze_with_regex(text)
        
    try:
        # Define known non-sensitive elements for different document types
        non_sensitive_terms = [
            # Common government headers
            "government of india", "govt of india", "government", "unique identification", "uidai", 
            "issued by", "verify", "signature", "male", "female", "gender", "help", "toll free", "authority",
            # Multilingual terms 
            "भारत सरकार", "सरकार", "प्राधिकरण", "इंडिया", "जारी किया गया",
            "இந்திய அரசு", "அரசு", "ஆணையம்", "வழங்கப்பட்டது",
            "ಭಾರತ ಸರ್ಕಾರ", "ಸರ್ಕಾರ", "ಪ್ರಾಧಿಕಾರ", "ನೀಡಿದ"
        ]
        
        # Add document-specific non-sensitive terms
        if document_type.lower() in ['aadhar', 'aadhaar']:
            non_sensitive_terms.extend([
                "aadhaar", "aadhar", "आधार", "ஆதார்", "ಆಧಾರ್", "ആധാർ", "ఆధార్",
                "identification number", "unique identification", "identification authority",
                "enrolment no", "enrollment no", "vid", "virtual id"
            ])
        
        prompt = f"""
        You are an expert document analyzer with a specialty in identifying sensitive information across multiple languages.
        
        First, analyze what type of document this is (ID card, resume, certificate, financial statement, medical record, etc.).
        
        CRUCIAL: You must identify ALL personal information regardless of language or format. Be extremely thorough.
        
        For Aadhar/Aadhaar cards, be EXTREMELY thorough in identifying ALL sensitive fields, including:
        - Full name (in any language)
        - Date of birth (in any format: MM/DD/YYYY, DD/MM/YYYY, or written in words)
        - Aadhar number (12 digits, may have spaces like: XXXX XXXX XXXX)
        - Complete address (including house number, street, village/city, state, pincode)
        - Gender information
        - Phone numbers
        - Email addresses
        - Parent/guardian names
        
        For all documents, carefully identify ANY sensitive personal information in ANY language:
        - English, Hindi, Tamil, Telugu, Kannada, Malayalam, or any other Indian language
        - Names often appear after "Name:", "नाम:", "பெயர்:", "ಹೆಸರು:", etc.
        - Addresses appear after "Address:", "पता:", "முகவரி:", "ವಿಳಾಸ:", etc.
        - DOB appears after "DOB:", "Date of Birth:", "जन्म तिथि:", "பிறந்த தேதி:", "ಹುಟ್ಟಿದ ದಿನಾಂಕ:", etc.
        
        DO NOT mark these as sensitive (these are document headers/labels):
        {", ".join(non_sensitive_terms)}
        
        Format your response as a JSON array with this structure:
        [
          {{
            "text": "the exact sensitive text",
            "category": "category name (Name, Address, Phone, Email, ID_Number, DOB, Financial)",
            "confidence": confidence score between 0-100
          }},
          ...
        ]
        
        Only output the JSON array, nothing else.
        
        Text to analyze:
        {text}
        """
        
       
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        }
        
     
        payload_json = json.dumps(payload)
        
      
        import subprocess
        import shlex
        
       
        curl_command = [
            'curl',
            'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent',
            '-H', 'Content-Type: application/json',
            '-H', f'X-goog-api-key: {GEMINI_API_KEY}',
            '-X', 'POST',
            '-d', payload_json
        ]
        
        # Execute the curl command
        print(f"Calling Gemini API with model: gemini-2.0-flash")
        print(f"API Key length: {len(GEMINI_API_KEY) if GEMINI_API_KEY else 'None'}")
        print(f"First 4 chars of API key: {GEMINI_API_KEY[:4] if GEMINI_API_KEY else 'None'}")
        print(f"Executing curl command: {' '.join([c if '-d' not in c and i == 0 else '...' for i, c in enumerate(curl_command)])}")
        
        process = subprocess.Popen(
            curl_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            print(f"Error calling Gemini API: {stderr}")
            return analyze_with_regex(text)
        
        # Debug the response
        print(f"Gemini API response received, length: {len(stdout)}")
        print(f"Response preview: {stdout[:200]}...")
        
        # Parse the response
        try:
            response_json = json.loads(stdout)
            
            # Extract text from response
            if "candidates" in response_json and len(response_json["candidates"]) > 0:
                candidate = response_json["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    response_text = candidate["content"]["parts"][0]["text"]
                    
                    # Find JSON content (between square brackets)
                    json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
                    if json_match:
                        json_content = json_match.group(0)
                    else:
                       
                        json_content = response_text
                        
                    # Clean the JSON content
                    json_content = json_content.strip()
                    
                    # Parse the JSON
                    try:
                        sensitive_fields = json.loads(json_content)
                        return sensitive_fields
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON from Gemini: {e}")
                        print(f"Raw response: {response_text}")
                        # Fall back to regex if JSON parsing fails
                        return analyze_with_regex(text)
            
            # If we couldn't extract the text correctly, fall back to regex
            print("Could not extract text from Gemini API response")
            return analyze_with_regex(text)
                
        except json.JSONDecodeError as e:
            print(f"Error parsing Gemini API response: {e}")
            print(f"Raw response: {stdout}")
            return analyze_with_regex(text)
            
    except Exception as e:
        print(f"Error using Gemini AI: {e}")
        # Fall back to regex-based analysis
        return analyze_with_regex(text)

def analyze_with_regex(text: str) -> List[Dict[str, Any]]:
    """
    Fallback function to analyze text using regex patterns.
    Used when Gemini API is not available or has an error.
    
    Args:
        text: The text to analyze
        
    Returns:
        A list of identified sensitive fields
    """
    sensitive_fields = []
    
    # Print for debugging
    print("\n========== USING REGEX FALLBACK ==========")
    print(f"Text length: {len(text)}")
    
    # Find potential names (capitalized words)
    name_matches = re.finditer(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', text)
    for match in name_matches:
        sensitive_fields.append({
            "text": match.group(),
            "category": "Name",
            "confidence": 85,
            "position": {"start": match.start(), "end": match.end()}
        })
    
    # More aggressive pattern for names with potential OCR errors
    name_alt_matches = re.finditer(r'\b[A-Z][a-z]{2,} +[A-Z][a-z]{2,}\b', text)
    for match in name_alt_matches:
        sensitive_fields.append({
            "text": match.group(),
            "category": "Name",
            "confidence": 75,
            "position": {"start": match.start(), "end": match.end()}
        })
    
    # Find names after common name labels in different languages
    name_label_patterns = [
        r'(?:Name|नाम|பெயர்|ಹೆಸರು|పేరు|പേര്)[\s\:]+([\w\s]+)',
        r'(?:S/o|D/o|W/o|C/o)[\s\:]+([\w\s]+)',
        r'(?:Father|Mother|Guardian)[\s\:]+([\w\s]+)',
    ]
    
    for pattern in name_label_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if match.group(1).strip():
                sensitive_fields.append({
                    "text": match.group(1).strip(),
                    "category": "Name",
                    "confidence": 90,
                    "position": {"start": match.start(1), "end": match.end(1)}
                })
    
    # Find Aadhar numbers (12 digits, may have spaces)
    aadhar_matches = re.finditer(r'\b\d{4}\s?\d{4}\s?\d{4}\b', text)
    for match in aadhar_matches:
        sensitive_fields.append({
            "text": match.group(),
            "category": "ID_Number",
            "confidence": 95,
            "position": {"start": match.start(), "end": match.end()}
        })
    
    # More forgiving pattern for Aadhar with potential OCR errors
    aadhar_alt_matches = re.finditer(r'\b\d{3,4}[\s\-]?\d{3,4}[\s\-]?\d{3,4}\b', text)
    for match in aadhar_alt_matches:
        if len(re.sub(r'[\s\-]', '', match.group())) >= 10:  # At least 10 digits
            sensitive_fields.append({
                "text": match.group(),
                "category": "ID_Number",
                "confidence": 85,
                "position": {"start": match.start(), "end": match.end()}
            })
    
    # Find text after Aadhar/Aadhaar labels
    aadhar_label_patterns = [
        r'(?:Aadhar|Aadhaar|आधार|ஆதார்|ಆಧಾರ್|ആധാർ)[\s\:]+([\d\s]{10,})',
        r'(?:UID|VID|यूआईडी|யூஐடி|ಯುಐಡಿ)[\s\:]+([\d\s]{10,})',
    ]
    
    for pattern in aadhar_label_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if match.group(1).strip():
                sensitive_fields.append({
                    "text": match.group(1).strip(),
                    "category": "ID_Number",
                    "confidence": 95,
                    "position": {"start": match.start(1), "end": match.end(1)}
                })
    
    # Find PAN numbers (10 characters, format: AAAAA0000A)
    pan_matches = re.finditer(r'\b[A-Z]{5}\d{4}[A-Z]\b', text)
    for match in pan_matches:
        sensitive_fields.append({
            "text": match.group(),
            "category": "ID_Number",
            "confidence": 95,
            "position": {"start": match.start(), "end": match.end()}
        })
    
    # Find email addresses
    email_matches = re.finditer(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', text)
    for match in email_matches:
        sensitive_fields.append({
            "text": match.group(),
            "category": "Email",
            "confidence": 90,
            "position": {"start": match.start(), "end": match.end()}
        })
    
    # Find phone numbers (10 digits)
    phone_matches = re.finditer(r'\b\d{10}\b', text)
    for match in phone_matches:
        sensitive_fields.append({
            "text": match.group(),
            "category": "Phone",
            "confidence": 85,
            "position": {"start": match.start(), "end": match.end()}
        })
    
    # Find phone numbers with country code or formatting
    phone_alt_matches = re.finditer(r'\b[\+]?[0-9]{1,3}[\s\-]?[0-9]{3,5}[\s\-]?[0-9]{3,5}\b', text)
    for match in phone_alt_matches:
        sensitive_fields.append({
            "text": match.group(),
            "category": "Phone",
            "confidence": 80,
            "position": {"start": match.start(), "end": match.end()}
        })
    
    # Find phone numbers after labels
    phone_label_patterns = [
        r'(?:Phone|Mobile|Tel|फोन|मोबाइल|फ़ोन|தொலைபேசி|மொபைல்|ಫೋನ್|ಮೊಬೈಲ್)[\s\:]+([\d\s\+\-]{8,})',
    ]
    
    for pattern in phone_label_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if match.group(1).strip():
                sensitive_fields.append({
                    "text": match.group(1).strip(),
                    "category": "Phone",
                    "confidence": 90,
                    "position": {"start": match.start(1), "end": match.end(1)}
                })
    
    # Find dates of birth (multiple formats)
    dob_matches = re.finditer(r'\b\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}\b', text)
    for match in dob_matches:
        sensitive_fields.append({
            "text": match.group(),
            "category": "DOB",
            "confidence": 80,
            "position": {"start": match.start(), "end": match.end()}
        })
    
    # Find dates in year-first format (ISO)
    dob_alt_matches = re.finditer(r'\b\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}\b', text)
    for match in dob_alt_matches:
        sensitive_fields.append({
            "text": match.group(),
            "category": "DOB",
            "confidence": 80,
            "position": {"start": match.start(), "end": match.end()}
        })
    
    # Find DOB after labels
    dob_label_patterns = [
        r'(?:DOB|Date of Birth|जन्म तिथि|பிறந்த தேதி|ಹುಟ್ಟಿದ ದಿನಾಂಕ|ജനന തീയതി|జన్మతేది)[\s\:]+([\d\s\-/\.]{6,})',
        r'(?:Born on|Birth Date)[\s\:]+([\d\s\-/\.]{6,})',
    ]
    
    for pattern in dob_label_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if match.group(1).strip():
                sensitive_fields.append({
                    "text": match.group(1).strip(),
                    "category": "DOB",
                    "confidence": 90,
                    "position": {"start": match.start(1), "end": match.end(1)}
                })
    
    # Find potential addresses (look for common keywords and patterns)
    address_matches = re.finditer(r'\b(?:No|#)\.?\s*\d+\s*,?.*?(?:Road|Street|Ave|Avenue|Blvd|Boulevard|Lane|Drive|Dr).*?(?:\d{5,6})?', text, re.IGNORECASE)
    for match in address_matches:
        if len(match.group()) > 10:  # Avoid too short matches
            sensitive_fields.append({
                "text": match.group(),
                "category": "Address",
                "confidence": 75,
                "position": {"start": match.start(), "end": match.end()}
            })
    
    # Find addresses after labels
    address_label_patterns = [
        r'(?:Address|Addr|पता|முகவரி|ವಿಳಾಸ|വിലാസം|చిరునామా)[\s\:]+([\w\s\d\-\.,/#]{10,})',
        r'(?:Residence|Res\.|Home)[\s\:]+([\w\s\d\-\.,/#]{10,})',
    ]
    
    for pattern in address_label_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            # Only include if match includes street/building details
            if match.group(1).strip() and len(match.group(1)) > 10:
                sensitive_fields.append({
                    "text": match.group(1).strip(),
                    "category": "Address",
                    "confidence": 85,
                    "position": {"start": match.start(1), "end": match.end(1)}
                })
    
    # Deduplicate fields with same text
    seen_texts = set()
    unique_fields = []
    for field in sensitive_fields:
        text_key = field["text"].lower()
        if text_key not in seen_texts:
            seen_texts.add(text_key)
            unique_fields.append(field)
    
    print(f"Regex found {len(unique_fields)} sensitive fields")
    print("=======================================\n")
    return unique_fields
    
def enhance_document_fields(extracted_fields: List[Dict[str, Any]], document_type: str = "unknown") -> List[Dict[str, Any]]:
    """
    Enhance existing OCR fields with AI-identified categories.
    This function uses Gemini AI to analyze all text and then maps the results
    back to the original OCR fields.
    
    Args:
        extracted_fields: The fields already extracted by OCR
        document_type: The type of document if known
        
    Returns:
        Enhanced fields with categories and confidence levels
    """
    # Skip if no fields
    if not extracted_fields:
        return []
        
    # Combine all text for analysis
    all_text = " ".join([field.get("text", "") for field in extracted_fields])
    
    # Get AI analysis of the text
    sensitive_info = analyze_document_text(all_text, document_type)
    
    # Map AI results back to the original fields
    enhanced_fields = []
    
    for field in extracted_fields:
        field_text = field.get("text", "")
        field_enhanced = False
        
        # Check if this field matches any identified sensitive information
        for info in sensitive_info:
            info_text = info.get("text", "")
            
            # Check for exact match or significant overlap
            if (field_text.lower() == info_text.lower() or 
                field_text.lower() in info_text.lower() or 
                info_text.lower() in field_text.lower() or
                # Check for 70% character overlap
                len(set(field_text.lower()) & set(info_text.lower())) > 0.7 * len(set(field_text.lower()))):
                
                # Enhance the field with AI-identified category
                enhanced_field = field.copy()
                enhanced_field["category"] = info.get("category", "Unknown")
                enhanced_field["ai_confidence"] = info.get("confidence", 70)
                enhanced_field["reason"] = info.get("reason", "Identified as sensitive information")
                enhanced_field["sensitive"] = True
                enhanced_fields.append(enhanced_field)
                field_enhanced = True
                break
        
        if not field_enhanced:
            # Keep the original field but mark as not sensitive
            enhanced_fields.append(field)
    
    return enhanced_fields

def map_coordinates(text_position: Dict[str, int], document_dimensions: Dict[str, int], field_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Maps text positions to document coordinates for redaction.
    
    Args:
        text_position: Position data from AI or regex (start/end indices)
        document_dimensions: Width and height of the document
        field_data: Original field data with page number
        
    Returns:
        Field data with coordinates for redaction
    """
    # If field data already has position data, use that
    if "position" in field_data:
        return field_data
        
    # Otherwise, create a dummy position (this would need to be improved in production)
    # This is a placeholder as we'd need to match text positions with OCR data
    start = text_position.get("start", 0)
    end = text_position.get("end", 0)
    
    # Create a position based on the text position
    # In a real implementation, this would map text indices to document coordinates
    position = {
        "x": 100,  # Placeholder
        "y": 100 + (start % 500),  # Placeholder
        "width": 200,
        "height": 30
    }
    
    field_data["position"] = position
    return field_data
