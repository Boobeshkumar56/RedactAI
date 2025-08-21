from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import uuid
import pytesseract
from PIL import Image
import pdf2image
import io
import json
import numpy as np
import cv2
import fitz  # PyMuPDF
import sys
import re
from redact_ai import redact_image, apply_custom_redactions
from ai_analysis import analyze_document_text, enhance_document_fields, map_coordinates

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # Get document type and language
    document_type = request.form.get('documentType', 'unknown')
    language = request.form.get('language', 'eng')  # Default to English if not specified
    
    # Generate a unique filename
    original_filename = file.filename
    file_extension = os.path.splitext(original_filename)[1].lower()
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
    
    # Save the file
    file.save(file_path)
    
    # Process the file based on type
    if file_extension in ['.pdf']:
        data_fields = extract_from_pdf(file_path, language)
    elif file_extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
        data_fields = extract_from_image(file_path, language)
    else:
        return jsonify({'error': 'Unsupported file type'}), 400
    
    return jsonify({
        'file_id': unique_filename,
        'original_filename': original_filename,
        'document_type': document_type,
        'language': language,
        'data_fields': data_fields
    })

def extract_from_pdf(file_path, language='eng'):
    data_fields = []
    
    # Convert PDF to images
    try:
        pdf_document = fitz.open(file_path)
        for page_num in range(pdf_document.page_count):
            page = pdf_document.load_page(page_num)
            pix = page.get_pixmap()
            
            # Convert pixmap to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Extract text using OCR with the specified language
            text = pytesseract.image_to_string(img, lang=language)
            
            # Get text blocks with positions
            page_data = extract_text_blocks(img, text, page_num, language)
            data_fields.extend(page_data)
    except Exception as e:
        print(f"Error processing PDF: {e}")
    
    return data_fields

def extract_from_image(file_path, language='eng'):
    try:
        img = Image.open(file_path)
        # Use the specified language for OCR
        text = pytesseract.image_to_string(img, lang=language)
        
        # Get text blocks with positions
        data_fields = extract_text_blocks(img, text, 0, language)
        return data_fields
    except Exception as e:
        print(f"Error processing image: {e}")
        return []

def extract_text_blocks(img, text, page_num, language='eng'):
    data_fields = []
    
    # Use pytesseract to get data with positions, specifying language
    data = pytesseract.image_to_data(img, lang=language, output_type=pytesseract.Output.DICT)
    
    n_boxes = len(data['text'])
    for i in range(n_boxes):
        if int(data['conf'][i]) > 60:  # Only consider text with confidence > 60%
            if data['text'][i].strip():
                x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                data_fields.append({
                    'id': str(uuid.uuid4()),
                    'text': data['text'][i],
                    'page': page_num,
                    'confidence': int(data['conf'][i]),
                    'position': {
                        'x': x,
                        'y': y,
                        'width': w,
                        'height': h
                    }
                })
    
    return data_fields

@app.route('/api/redact', methods=['POST'])
def redact_document():
    data = request.json
    file_id = data.get('file_id')
    redactions = data.get('redactions', [])
    redaction_type = data.get('redaction_type', 'temporary')
    document_type = data.get('document_type', 'unknown')
    language = data.get('language', 'eng')  # Default to English if not specified
    
    if not file_id:
        return jsonify({'error': 'No file_id provided'}), 400
    
    file_path = os.path.join(UPLOAD_FOLDER, file_id)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    file_extension = os.path.splitext(file_id)[1].lower()
    output_path = os.path.join(PROCESSED_FOLDER, f"redacted_{file_id}")
    
    if file_extension == '.pdf':
        apply_pdf_redactions(file_path, output_path, redactions, redaction_type, document_type, language)
    else:
        apply_image_redactions(file_path, output_path, redactions, redaction_type, document_type, language)
    
    return jsonify({
        'redacted_file_id': f"redacted_{file_id}",
        'redaction_type': redaction_type
    })

def apply_pdf_redactions(file_path, output_path, redactions, default_redaction_type, document_type='unknown', language='eng'):
    """Process PDF redaction with support for document-type based automatic redaction"""
    pdf_document = fitz.open(file_path)
    
    # For manual redactions provided by user
    if len(redactions) > 0:
        for redaction in redactions:
            page_num = redaction.get('page', 0)
            redact_method = redaction.get('method', 'select')  # 'select' or 'brush'
            # Use redaction-specific type if provided, otherwise use the default
            redaction_type = redaction.get('redaction_type', default_redaction_type)
            
            if page_num < pdf_document.page_count:
                page = pdf_document.load_page(page_num)
                
                # Get position
                pos = redaction.get('position', {})
                rect = fitz.Rect(
                    pos.get('x', 0),
                    pos.get('y', 0),
                    pos.get('x', 0) + pos.get('width', 0),
                    pos.get('y', 0) + pos.get('height', 0)
                )
                
                if redaction_type == 'permanent':
                    # Permanent redaction - black rectangle
                    page.add_redact_annot(rect)
                    page.apply_redactions()
                else:
                    # Temporary redaction
                    if redact_method == 'brush':
                        # Yellow highlight for brush
                        page.draw_rect(rect, color=(1, 0.9, 0), fill=(1, 0.9, 0, 0.5))
                    else:
                        # Gray highlight for selection
                        page.draw_rect(rect, color=(0.7, 0.7, 0.7), fill=(0.7, 0.7, 0.7, 0.5))
    
    # For template-based redactions of known document types (when no manual redactions)
    elif document_type in ['aadhar', 'aadhaar', 'pan', 'passport']:
        # Get fields to redact from document type
        doc_fields = {
            'aadhaar': ['name', 'aadhaar_number', 'dob', 'address'],
            'aadhar': ['name', 'aadhaar_number', 'dob', 'address'],
            'pan': ['name', 'pan_number', 'dob'],
            'passport': ['name', 'passport_number', 'dob', 'nationality']
        }
        
        fields = doc_fields.get(document_type, [])
        permanent_fields = fields if default_redaction_type == 'permanent' else []
        temporary_fields = fields if default_redaction_type != 'permanent' else []
        
        # Process each page individually
        for page_num in range(pdf_document.page_count):
            # Extract page as image
            page = pdf_document.load_page(page_num)
            pix = page.get_pixmap()
            
            # Convert to PIL Image for processing
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Create a temporary file for the image
            temp_img_path = f"temp_page_{page_num}.png"
            img.save(temp_img_path)
            
            # Use our redaction engine on this page
            redacted_img = redact_image(
                image_path=temp_img_path,
                doc_type=document_type,
                permanent_fields=permanent_fields,
                temporary_fields=temporary_fields,
                style=default_redaction_type,
                lang=language,
                debug=True
            )
            
            # Save the redacted image temporarily
            redacted_temp_path = f"redacted_temp_page_{page_num}.png"
            redacted_img.save(redacted_temp_path)
            
            # Replace the PDF page with the redacted image
            img_rect = page.rect
            page.insert_image(img_rect, filename=redacted_temp_path)
            
            # Clean up temporary files
            try:
                os.remove(temp_img_path)
                os.remove(redacted_temp_path)
            except:
                pass
    
    pdf_document.save(output_path)
    pdf_document.close()

def apply_image_redactions(file_path, output_path, redactions, redaction_type, document_type='unknown', language='eng'):
    """Process image redaction using the advanced redaction library"""
    try:
        # If we have manual redactions, always use those first
        if len(redactions) > 0:
            # Use custom redactions based on coordinates
            img = apply_custom_redactions(file_path, redactions, redaction_type)
            cv2.imwrite(output_path, img)
        # For template-based redactions (common fields in known document types)
        elif document_type in ['aadhar', 'aadhaar', 'pan', 'passport']:
            permanent_fields = []
            temporary_fields = []
            
            # Get fields to redact from document type
            doc_fields = {
                'aadhaar': ['name', 'aadhaar_number', 'dob', 'address'],
                'aadhar': ['name', 'aadhaar_number', 'dob', 'address'],
                'pan': ['name', 'pan_number', 'dob'],
                'passport': ['name', 'passport_number', 'dob', 'nationality']
            }
            
            fields = doc_fields.get(document_type, [])
            
            if redaction_type == 'permanent':
                permanent_fields = fields
            else:
                temporary_fields = fields
                
            # Use the advanced redaction library
            img = redact_image(
                image_path=file_path,
                doc_type=document_type,
                permanent_fields=permanent_fields,
                temporary_fields=temporary_fields,
                style=redaction_type,
                lang=language,  # Pass the language parameter
                debug=True  # Enable debug to see detected fields
            )
            img.save(output_path)
        else:
            # For unknown document types with no manual redactions
            img = cv2.imread(file_path)
            cv2.imwrite(output_path, img)
            
    except Exception as e:
        print(f"Error in image redaction: {str(e)}")
        # Fallback to basic redaction
        img = cv2.imread(file_path)
        
        for redaction in redactions:
            # Get position
            pos = redaction.get('position', {})
            x = pos.get('x', 0)
            y = pos.get('y', 0)
            w = pos.get('width', 0)
            h = pos.get('height', 0)
            redact_method = redaction.get('method', 'select')
            # Use redaction-specific type if provided, otherwise use the default
            redaction_type_specific = redaction.get('redaction_type', redaction_type)
            
            # Choose color based on redaction type and method
            if redaction_type_specific == 'permanent':
                # Black for permanent
                color = (0, 0, 0)
            else:
                if redact_method == 'brush':
                    # Yellow for temporary brush
                    color = (0, 255, 255)  # BGR format
                else:
                    # Gray for temporary select
                    color = (192, 192, 192)  # BGR format
                
            # Apply rectangle with the chosen color
            cv2.rectangle(img, (x, y), (x + w, y + h), color, -1)
        
        cv2.imwrite(output_path, img)


def map_coordinates(text_position, document_dimensions, field_data):
    """
    Maps text positions from AI analysis to document coordinates for redaction.
    
    Args:
        text_position: Position data from AI (start/end indices in text)
        document_dimensions: Width and height of the document
        field_data: Original field data with the text
        
    Returns:
        Field data with coordinates for redaction
    """
    # If the field already has position info, use that
    if 'position' in field_data and isinstance(field_data['position'], dict) and 'x' in field_data['position']:
        return field_data
        
    # Get text and document dimensions
    text = field_data.get('text', '')
    doc_width = document_dimensions.get('width', 800)
    doc_height = document_dimensions.get('height', 1000)
    page = field_data.get('page', 0)
    
    # Calculate position based on text position in document
    # This is a simplified approach - in a real implementation, 
    # you would use OCR data to get actual coordinates
    
    # Default position (centered)
    position = {
        'x': int(doc_width * 0.2),
        'y': int(doc_height * 0.2) + (50 * page),
        'width': max(len(text) * 10, 100),  # Width based on text length
        'height': 30
    }
    
    # If we have text start/end position, use it to calculate y position
    if isinstance(text_position, dict) and 'start' in text_position and 'end' in text_position:
        start = text_position.get('start', 0)
        
        # Try to use the start position to approximate y-coordinate
        # This assumes text flows from top to bottom
        y_ratio = min(start / 5000, 0.9)  # Normalize position (assumes max 5000 chars)
        position['y'] = int(doc_height * y_ratio)
    
    # Add position to field data
    field_data['position'] = position
    return field_data

@app.route('/api/get_supported_languages', methods=['GET'])
def get_supported_languages():
    """Return a list of supported languages for OCR"""
    # List of languages we support with our keyword patterns
    supported_languages = [
        {"code": "eng", "name": "English"},
        {"code": "tam", "name": "Tamil"},
        {"code": "kan", "name": "Kannada"},
        {"code": "hin", "name": "Hindi"},
        {"code": "tel", "name": "Telugu"},
        {"code": "mal", "name": "Malayalam"}
    ]
    
    # We also support multiple languages by using + notation (e.g., "eng+tam")
    combined_languages = [
        {"code": "eng+tam", "name": "English + Tamil"},
        {"code": "eng+hin", "name": "English + Hindi"},
        {"code": "eng+tel", "name": "English + Telugu"},
        {"code": "eng+kan", "name": "English + Kannada"},
        {"code": "eng+mal", "name": "English + Malayalam"}
    ]
    
    return jsonify({
        "languages": supported_languages,
        "combined_languages": combined_languages
    })

@app.route('/api/download/<file_id>', methods=['GET'])
def download_file(file_id):
    print(f"Download request for file: {file_id}")
    file_path = os.path.join(PROCESSED_FOLDER, file_id)
    
    # First try the processed folder
    if os.path.exists(file_path):
        print(f"Found file in processed folder: {file_path}")
        return send_file(file_path, as_attachment=True)
    
    # If not found in processed, try the uploads folder
    file_path = os.path.join(UPLOAD_FOLDER, file_id)
    if os.path.exists(file_path):
        print(f"Found file in uploads folder: {file_path}")
        return send_file(file_path, as_attachment=True)
    
    print(f"File not found: {file_id}")
    return jsonify({'error': 'File not found'}), 404

@app.route('/api/analyze-document', methods=['POST'])
def analyze_document():
    """
    API endpoint to analyze documents using AI for identifying sensitive information.
    
    Expected JSON input:
    {
        "file_id": "unique_file_id.ext",
        "document_type": "aadhar|pan|passport|unknown",
        "extracted_text": "Text from the document (optional)",
        "data_fields": [{ "id": "...", "text": "...", ... }] (optional)
    }
    
    Returns JSON with identified sensitive fields.
    """
    try:
        data = request.json
        file_id = data.get('file_id')
        document_type = data.get('document_type', 'unknown')
        
        if not file_id:
            return jsonify({'error': 'No file_id provided'}), 400
        
        file_path = os.path.join(UPLOAD_FOLDER, file_id)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        # Default document dimensions
        doc_width = 800
        doc_height = 1100
        
        # If data fields are provided, enhance them with AI analysis
        if 'data_fields' in data and data['data_fields']:
            data_fields = data['data_fields']
            # Extract text from data fields for AI analysis
            all_text = " ".join([field.get("text", "") for field in data_fields if field.get("text")])
            
            # If we have text, use Gemini to analyze and enhance fields
            if all_text:
                # Use the enhanced_document_fields function from ai_analysis.py
                enhanced_fields = enhance_document_fields(data_fields, document_type)
                
                # Filter to only include fields identified as sensitive
                sensitive_fields = [field for field in enhanced_fields if field.get('category') or field.get('ai_confidence')]
                
                return jsonify({
                    'original_fields': data_fields,
                    'sensitive_fields': sensitive_fields,
                    'analysis_type': 'gemini_ai'
                })
            
        # If text is provided directly, use it
        elif 'extracted_text' in data and data['extracted_text']:
            extracted_text = data['extracted_text']
            
        # Otherwise, extract text from the file
        else:
            file_extension = os.path.splitext(file_id)[1].lower()
            
            if file_extension == '.pdf':
                # Extract text from PDF
                extracted_text = ""
                try:
                    pdf_document = fitz.open(file_path)
                    
                    # Get document dimensions for coordinate mapping
                    if pdf_document.page_count > 0:
                        first_page = pdf_document.load_page(0)
                        doc_width = first_page.rect.width
                        doc_height = first_page.rect.height
                    
                    # Process each page
                    for page_num in range(pdf_document.page_count):
                        page = pdf_document.load_page(page_num)
                        extracted_text += page.get_text()
                except Exception as e:
                    print(f"Error extracting text from PDF: {e}")
                    return jsonify({'error': f'Failed to extract text from PDF: {str(e)}'}), 500
            else:
                # Extract text from image
                try:
                    img = Image.open(file_path)
                    extracted_text = pytesseract.image_to_string(img)
                    
                    # Get document dimensions
                    doc_width = img.width
                    doc_height = img.height
                except Exception as e:
                    print(f"Error extracting text from image: {e}")
                    return jsonify({'error': f'Failed to extract text from image: {str(e)}'}), 500
        
        # Use Gemini to analyze the text
        sensitive_fields = analyze_document_text(extracted_text, document_type)
        
        # Generate field IDs and add page number
        for i, field in enumerate(sensitive_fields):
            field['id'] = f"ai-field-{i}-{uuid.uuid4()}"
            field['page'] = 0  # Default to first page
            field['method'] = 'select'
            
            # If we have position info from text analysis, map it to document coordinates
            if 'position' in field:
                field = map_coordinates(
                    field['position'], 
                    {'width': doc_width, 'height': doc_height}, 
                    field
                )
            else:
                # Create a default position if none exists
                field['position'] = {
                    'x': int(doc_width * 0.1),
                    'y': int(doc_height * 0.1) + (i * 50),  # Stagger vertically
                    'width': max(len(field.get('text', '')) * 8, 100),  # Width based on text length
                    'height': 30
                }
        
        return jsonify({
            'sensitive_fields': sensitive_fields,
            'analysis_type': 'gemini_ai'
        })
        
    except Exception as e:
        print(f"Error in AI analysis: {str(e)}")
        return jsonify({'error': f'AI analysis failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
