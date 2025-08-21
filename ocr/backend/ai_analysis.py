import os
import json
import re
import subprocess
import shlex
from typing import List, Dict, Any, Optional

"""
This file contains the code for AI-based document analysis.
It integrates with Google's Gemini AI to identify sensitive information in documents.
"""


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDzBsP9iA21qepnVd8PIdQad3CisrX0V-Q")

def analyze_document_text(text: str, document_type: str = "unknown") -> List[Dict[str, Any]]:
    """
    Analyze document text to identify sensitive information using Gemini AI.
    
    Args:
        text: The extracted text from the document
        document_type: The type of document if known
        
    Returns:
        A list of identified sensitive fields with their categories
    """
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
        First, analyze the text to determine what type of document this is (e.g., resume, identity card, certificate, financial statement, medical record, etc.).
        
        Then, based on the document type, identify ONLY genuine personal/sensitive information. For example:
        - In a course certificate: identify the person's name but DON'T mark completion dates as DOB
        - In a resume: identify contact details but DON'T mark job titles or skills as sensitive
        - In an ID card: identify personal information but DON'T mark document headers, titles, or labels
        
        Consider the document context before classifying fields. Only mark information as sensitive if it reveals personal identifiable information about an individual.
        
        DO NOT mark these elements as sensitive (these are document headers/labels, not sensitive information):
        {", ".join(non_sensitive_terms)}
        
        Identify these types of information:
        - Full names of individuals
        - Physical addresses (home, mailing)
        - Phone numbers
        - Email addresses
        - ID numbers (Aadhar, PAN, passport, SSN, etc.)
        - Actual dates of birth (not other dates)
        - Financial information (account numbers, credit cards)
        
        Format your response as a JSON array with the following structure:
        [
          {{
            "text": "the exact sensitive text",
            "category": "category name (Name, Address, Phone, Email, ID_Number, DOB, Financial)",
            "confidence": confidence score between 0-100,
            "reason": "brief explanation of why this is sensitive in this document context"
          }},
          ...
        ]
        
        Only output the JSON array, nothing else.
        This should work for multilingual text (English, Hindi, Tamil, Telugu, Kannada, Malayalam, etc.)
        
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
    
    # Find potential names (capitalized words)
    name_matches = re.finditer(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', text)
    for match in name_matches:
        sensitive_fields.append({
            "text": match.group(),
            "category": "Name",
            "confidence": 85,
            "position": {"start": match.start(), "end": match.end()}
        })
    
    # Find Aadhar numbers (12 digits, may have spaces)
    aadhar_matches = re.finditer(r'\b\d{4}\s?\d{4}\s?\d{4}\b', text)
    for match in aadhar_matches:
        sensitive_fields.append({
            "text": match.group(),
            "category": "Aadhar Number",
            "confidence": 95,
            "position": {"start": match.start(), "end": match.end()}
        })
    
    # Find PAN numbers (10 characters, format: AAAAA0000A)
    pan_matches = re.finditer(r'\b[A-Z]{5}\d{4}[A-Z]\b', text)
    for match in pan_matches:
        sensitive_fields.append({
            "text": match.group(),
            "category": "PAN",
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
            "category": "Phone Number",
            "confidence": 85,
            "position": {"start": match.start(), "end": match.end()}
        })
    
    # Find dates of birth
    dob_matches = re.finditer(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b', text)
    for match in dob_matches:
        sensitive_fields.append({
            "text": match.group(),
            "category": "Date of Birth",
            "confidence": 80,
            "position": {"start": match.start(), "end": match.end()}
        })
    
    return sensitive_fields
    
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
