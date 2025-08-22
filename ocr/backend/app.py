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
    
    # Get language
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
            
            # First try to extract text directly from PDF
            direct_text = page.get_text()
            
            # Check if we got meaningful text directly
            if len(direct_text.strip()) > 100:
                print(f"Page {page_num}: Using direct PDF text extraction")
                # Create a synthetic data field with the extracted text
                data_fields.append({
                    'id': str(uuid.uuid4()),
                    'text': direct_text,
                    'page': page_num,
                    'confidence': 90,
                    'extraction_method': 'direct_pdf'
                })
            else:
                # If not enough text was extracted directly, use OCR
                print(f"Page {page_num}: Using OCR text extraction with language '{language}'")
                pix = page.get_pixmap(alpha=False)
                
                # Convert pixmap to PIL Image
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                # Extract text using OCR with the specified language
                # Use psm=3 for automatic page segmentation
                custom_config = f'--oem 3 --psm 3 -l {language}'
                text = pytesseract.image_to_string(img, config=custom_config)
                
                # Extract text using OCR
                text = pytesseract.image_to_string(img, config=custom_config)
                
                # Get text blocks with positions
                page_data = extract_text_blocks(img, text, page_num, language)
                data_fields.extend(page_data)
    except Exception as e:
        print(f"Error processing PDF: {e}")
    
    return data_fields

def extract_from_image(file_path, language='eng'):
    try:
        img = Image.open(file_path)
        
        # Print image details for debugging
        print(f"Processing image: {file_path}")
        print(f"Image size: {img.size}, format: {img.format}, mode: {img.mode}")
        
        # Use the specified language for OCR with custom configuration
        # Use psm=3 for automatic page segmentation
        custom_config = f'--oem 3 --psm 3 -l {language}'
        text = pytesseract.image_to_string(img, config=custom_config)
        
        # Get text blocks with positions
        data_fields = extract_text_blocks(img, text, 0, language)
        
        # If we got very few text blocks, try preprocessing the image
        if len(data_fields) < 5:
            print("Few text blocks detected, trying image preprocessing...")
            # Convert to cv2 format for preprocessing
            img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            
            # Convert to grayscale
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            
            # Apply adaptive thresholding
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                          cv2.THRESH_BINARY, 11, 2)
            
            # Convert back to PIL
            img_processed = Image.fromarray(thresh)
            
            # Try OCR again with the processed image
            text = pytesseract.image_to_string(img_processed, config=custom_config)
            
            # Get text blocks with positions from processed image
            data_fields_processed = extract_text_blocks(img_processed, text, 0, language)
            
            # Use the better result (more text blocks)
            if len(data_fields_processed) > len(data_fields):
                print(f"Using processed image results: {len(data_fields_processed)} blocks vs {len(data_fields)} blocks")
                data_fields = data_fields_processed
        
        return data_fields
    except Exception as e:
        print(f"Error processing image: {e}")
        return []

def extract_text_blocks(img, text, page_num, language='eng'):
    data_fields = []
    
    # Configure tesseract parameters for better multi-language support
    custom_config = f'--oem 3 --psm 3 -l {language}'
    
    try:
        # Use pytesseract to get data with positions, specifying language and config
        data = pytesseract.image_to_data(img, config=custom_config, output_type=pytesseract.Output.DICT)
        
        # Debug: Print OCR confidence stats
        confidences = [int(conf) for conf in data['conf'] if conf != '-1']
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
        
        # Process detected text blocks
        n_boxes = len(data['text'])
        for i in range(n_boxes):
            # Use a lower confidence threshold for non-English languages
            conf_threshold = 40 if language != 'eng' else 60
            
            if int(data['conf'][i]) > conf_threshold:  # Lower threshold for better multi-language detection
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
                        },
                        'language': language
                    })
        
        # If we got very few blocks but have text, create a synthetic block with all text
        if len(data_fields) < 3 and text.strip():
            # Create a synthetic field with the full text
            data_fields.append({
                'id': str(uuid.uuid4()),
                'text': text,
                'page': page_num,
                'confidence': 70,  # Moderate confidence for the whole text
                'position': {
                    'x': 10,
                    'y': 10,
                    'width': img.width - 20,
                    'height': img.height - 20
                },
                'language': language,
                'synthetic': True
            })
    
    except Exception as e:
        print(f"Error in text block extraction: {e}")
        # Create a fallback field with the raw text
        if text.strip():
            data_fields.append({
                'id': str(uuid.uuid4()),
                'text': text,
                'page': page_num,
                'confidence': 50,  # Lower confidence for fallback method
                'position': {
                    'x': 10,
                    'y': 10,
                    'width': img.width - 20 if hasattr(img, 'width') else 800,
                    'height': img.height - 20 if hasattr(img, 'height') else 1000
                },
                'language': language,
                'fallback': True
            })
    
    return data_fields

def apply_pdf_text_redactions(file_path, output_path, text_to_redact, language='eng'):
    """Find and redact specific text in PDF by searching for typed text"""
    pdf_document = fitz.open(file_path)
    success_count = 0
    
    try:
        for page_num in range(pdf_document.page_count):
            page = pdf_document.load_page(page_num)
            
            for redaction_item in text_to_redact:
                search_text = redaction_item.get('text', '').strip()
                redaction_type = redaction_item.get('redaction_type', 'temporary')
                case_sensitive = redaction_item.get('case_sensitive', False)
                
                if not search_text:
                    continue
                
                # Search for the text on this page
                text_instances = page.search_for(search_text, flags=0 if case_sensitive else fitz.TEXT_SEARCH_INSENSITIVE)
                
                for rect in text_instances:
                    # Expand the rectangle slightly to ensure full coverage
                    expanded_rect = fitz.Rect(
                        rect.x0 - 2,  # Add padding
                        rect.y0 - 2,
                        rect.x1 + 2,
                        rect.y1 + 2
                    )
                    
                    if redaction_type == 'permanent':
                        # Permanent redaction - black rectangle
                        page.add_redact_annot(expanded_rect)
                        page.apply_redactions()
                    else:
                        # Temporary redaction - yellow highlight
                        page.draw_rect(expanded_rect, color=(1, 0.9, 0), fill=(1, 0.9, 0, 0.7))
                        # Add border for better visibility
                        page.draw_rect(expanded_rect, color=(0, 0, 0), width=0.5)
                    
                    success_count += 1
                
                # If no instances found on this page and we're using plain text search
                # Try using a more relaxed search by breaking text into words
                if len(text_instances) == 0 and len(search_text.split()) > 1:
                    words = search_text.split()
                    
                    for word in words:
                        if len(word) < 3:  # Skip very short words
                            continue
                            
                        word_instances = page.search_for(word, flags=0 if case_sensitive else fitz.TEXT_SEARCH_INSENSITIVE)
                        
                        for rect in word_instances:
                            # Expand the rectangle slightly to ensure full coverage
                            expanded_rect = fitz.Rect(
                                rect.x0 - 2,
                                rect.y0 - 2,
                                rect.x1 + 2,
                                rect.y1 + 2
                            )
                            
                            if redaction_type == 'permanent':
                                # Permanent redaction - black rectangle
                                page.add_redact_annot(expanded_rect)
                                page.apply_redactions()
                            else:
                                # Temporary redaction - yellow highlight
                                page.draw_rect(expanded_rect, color=(1, 0.9, 0), fill=(1, 0.9, 0, 0.7))
                            # Add border for better visibility
                            page.draw_rect(expanded_rect, color=(0, 0, 0), width=0.5)
                            
                            success_count += 1        # Apply all permanent redactions after processing
        pdf_document.save(output_path)
        
    except Exception as e:
        # Fallback: copy original file
        pdf_document.save(output_path)
    finally:
        pdf_document.close()
    
    return success_count

def apply_image_text_redactions(file_path, output_path, text_to_redact, language='eng'):
    """Find and redact specific text in images by using OCR to locate typed text"""
    success_count = 0
    try:
        img_cv = cv2.imread(file_path)
        if img_cv is None:
            raise FileNotFoundError(f"Cannot read image: {file_path}")
        
        # Convert to PIL for OCR
        img_pil = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
        
        # Get OCR data with bounding boxes
        custom_config = f'--oem 3 --psm 3 -l {language}'
        ocr_data = pytesseract.image_to_data(img_pil, config=custom_config, output_type=pytesseract.Output.DICT)
        
        # Print OCR text for debugging
        ocr_data = pytesseract.image_to_data(img_pil, config=custom_config, output_type=pytesseract.Output.DICT)
        
        for redaction_item in text_to_redact:
            search_text = redaction_item.get('text', '').strip()
            redaction_type = redaction_item.get('redaction_type', 'temporary')
            case_sensitive = redaction_item.get('case_sensitive', False)
            
            if not search_text:
                continue
            
            # Search for the text in OCR results - exact matches
            exact_matches = 0
            for i in range(len(ocr_data['text'])):
                ocr_text = ocr_data['text'][i].strip()
                
                # Check if this OCR text matches our search text
                if case_sensitive:
                    text_match = search_text in ocr_text
                else:
                    text_match = search_text.lower() in ocr_text.lower()
                
                if text_match and int(ocr_data['conf'][i]) > 30:  # Only consider confident matches
                    # Get bounding box
                    x = ocr_data['left'][i]
                    y = ocr_data['top'][i]
                    w = ocr_data['width'][i]
                    h = ocr_data['height'][i]
                    
                    # Expand the box slightly to ensure full coverage
                    x = max(0, x - 5)
                    y = max(0, y - 5)
                    w = w + 10
                    h = h + 10
                    
                    if redaction_type == 'permanent':
                        # Black box for permanent redaction
                        cv2.rectangle(img_cv, (x, y), (x + w, y + h), (0, 0, 0), -1)
                        cv2.rectangle(img_cv, (x, y), (x + w, y + h), (255, 255, 255), 2)
                    else:
                        # Yellow box for temporary redaction
                        cv2.rectangle(img_cv, (x, y), (x + w, y + h), (0, 255, 255), -1)
                        cv2.rectangle(img_cv, (x, y), (x + w, y + h), (0, 0, 0), 2)
                    
                    success_count += 1
                    exact_matches += 1
                    print(f"Exact match redacted: '{search_text}' in OCR text: '{ocr_text}'")
            
            # If no exact matches found, try word-by-word search
            if exact_matches == 0 and len(search_text.split()) > 1:
                words = search_text.split()
                print(f"No exact match found. Trying word-by-word search for '{search_text}'")
                
                for word in words:
                    if len(word) < 3:  # Skip very short words
                        continue
                    
                    for i in range(len(ocr_data['text'])):
                        ocr_text = ocr_data['text'][i].strip()
                        
                        # Check if this OCR text contains our word
                        if case_sensitive:
                            word_match = word in ocr_text
                        else:
                            word_match = word.lower() in ocr_text.lower()
                        
                        if word_match and int(ocr_data['conf'][i]) > 30:
                            # Get bounding box
                            x = ocr_data['left'][i]
                            y = ocr_data['top'][i]
                            w = ocr_data['width'][i]
                            h = ocr_data['height'][i]
                            
                            # Expand the box slightly
                            x = max(0, x - 5)
                            y = max(0, y - 5)
                            w = w + 10
                            h = h + 10
                            
                            if redaction_type == 'permanent':
                                # Black box for permanent redaction
                                cv2.rectangle(img_cv, (x, y), (x + w, y + h), (0, 0, 0), -1)
                                cv2.rectangle(img_cv, (x, y), (x + w, y + h), (255, 255, 255), 2)
                            else:
                                # Yellow box for temporary redaction
                                cv2.rectangle(img_cv, (x, y), (x + w, y + h), (0, 255, 255), -1)
                                cv2.rectangle(img_cv, (x, y), (x + w, y + h), (0, 0, 0), 2)
                            
                            success_count += 1
                            print(f"Word match redacted: '{word}' from '{search_text}' in OCR text: '{ocr_text}'")
        
        cv2.imwrite(output_path, img_cv)
        
    except Exception as e:
        # Fallback: copy original file
        import shutil
        shutil.copy2(file_path, output_path)
        success_count = 0
    
    return success_count

@app.route('/api/redact', methods=['POST'])
def redact_document():
    data = request.json
    file_id = data.get('file_id')
    redactions = data.get('redactions', [])
    text_to_redact = data.get('text_to_redact', [])  # Text-based redaction
    redaction_type = data.get('redaction_type', 'temporary')
    language = data.get('language', 'eng')
    
    if not file_id:
        return jsonify({'error': 'No file_id provided'}), 400
    
    file_path = os.path.join(UPLOAD_FOLDER, file_id)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    file_extension = os.path.splitext(file_id)[1].lower()
    output_path = os.path.join(PROCESSED_FOLDER, f"redacted_{file_id}")
    
    total_redactions = 0
    
    # Handle text-based redaction (manual typing method)
    if text_to_redact:
        if file_extension == '.pdf':
            total_redactions = apply_pdf_text_redactions(file_path, output_path, text_to_redact, language)
        else:
            total_redactions = apply_image_text_redactions(file_path, output_path, text_to_redact, language)
        return jsonify({
            'redacted_file_id': f"redacted_{file_id}",
            'total_redactions': total_redactions,
            'redaction_method': 'manual_typing'
        })
    
    # Handle coordinate-based redaction (field selection) or AI redaction
    elif redactions:
        if file_extension == '.pdf':
            apply_pdf_redactions(file_path, output_path, redactions, redaction_type, 'unknown', language)
        else:
            apply_image_redactions(file_path, output_path, redactions, redaction_type, 'unknown', language)
        
        return jsonify({
            'redacted_file_id': f"redacted_{file_id}",
            'redaction_type': redaction_type,
            'redaction_method': 'coordinate_based'
        })
    
    else:
        return jsonify({'error': 'No redaction method specified'}), 400

def apply_pdf_redactions(file_path, output_path, redactions, default_redaction_type, document_type='unknown', language='eng'):
    """Process PDF redaction with support for document-type based automatic redaction"""
    pdf_document = fitz.open(file_path)
    
    # For manual redactions provided by user
    if len(redactions) > 0:
        for redaction in redactions:
            page_num = redaction.get('page', 0)
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
                    # Temporary redaction - Gray highlight for selection
                    page.draw_rect(rect, color=(0.7, 0.7, 0.7), fill=(0.7, 0.7, 0.7, 0.5))
    
    # For template-based redactions of known document types (when no manual redactions)
    else:
        # Check if the document appears to be an ePDF (digital PDF) vs scanned image
        is_epdf = False
        text_content = ""
        
        # First check a sample page for selectable text
        if pdf_document.page_count > 0:
            sample_page = pdf_document.load_page(0)
            text_content = sample_page.get_text()
            # If we have substantial text content, it's likely an ePDF
            is_epdf = len(text_content) > 100
        
        # Determine the exact document type based on content
        detected_doc_type = document_type
        
        # For ePDFs, we can try to be more specific about which template to use
        if is_epdf:
            # For Aadhar cards
            if document_type.lower() in ['aadhar', 'aadhaar']:
                if "GOVERNMENT OF INDIA" in text_content and "UNIQUE IDENTIFICATION AUTHORITY" in text_content:
                    # This is likely an e-Aadhaar download
                    detected_doc_type = "eaadhaar"
                    print(f"Detected ePDF type: eaadhaar")
            
            # For PAN cards
            elif document_type.lower() == 'pan':
                if "INCOME TAX DEPARTMENT" in text_content and "GOVT. OF INDIA" in text_content:
                    # This is likely an e-PAN download
                    detected_doc_type = "epan"
                    print(f"Detected ePDF type: epan")
            
            # For direct PDF redaction, using PyMuPDF's annotation capabilities
            if detected_doc_type in ['eaadhaar', 'epan']:
                from redact_ai import TEMPLATES
                
                template = TEMPLATES.get(detected_doc_type, {})
                
                # Get fields to redact based on document type
                doc_fields = {
                    'aadhaar': ['name', 'aadhaar_number', 'dob', 'address', 'parent_name'],
                    'aadhar': ['name', 'aadhaar_number', 'dob', 'address', 'parent_name'],
                    'eaadhaar': ['name', 'aadhaar_number', 'dob', 'address', 'gender', 'photo', 'qr_code'],
                    'pan': ['name', 'pan_number', 'dob', 'father_name'],
                    'epan': ['name', 'pan_number', 'dob', 'photo'],
                    'passport': ['name', 'passport_number', 'dob', 'nationality', 'place_of_birth', 'photo']
                }
                
                fields_to_redact = doc_fields.get(detected_doc_type, [])
                
                # Process each page with template coordinates
                for page_num in range(pdf_document.page_count):
                    page = pdf_document.load_page(page_num)
                    page_width = page.rect.width
                    page_height = page.rect.height
                    
                    for field in fields_to_redact:
                        if field in template:
                            coords = template[field]
                            x = int(coords['x'] * page_width)
                            y = int(coords['y'] * page_height)
                            width = int(coords['w'] * page_width)
                            height = int(coords['h'] * page_height)
                            
                            rect = fitz.Rect(x, y, x + width, y + height)
                            
                            if default_redaction_type == 'permanent':
                                # Add permanent redaction
                                page.add_redact_annot(rect)
                                page.apply_redactions()
                            else:
                                # Add temporary redaction (yellow highlight)
                                page.draw_rect(rect, color=(1, 0.9, 0), fill=(1, 0.9, 0, 0.5))
                
                print(f"Applied template-based redactions for ePDF {detected_doc_type}")
                pdf_document.save(output_path)
                pdf_document.close()
                return
        
        # For non-ePDFs or if we didn't perform direct PDF redaction, use image-based redaction
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
            img_cv = cv2.imread(file_path)
            if img_cv is None:
                raise FileNotFoundError(f"Cannot read image: {file_path}")
            
            # Apply box redactions
            for redaction in redactions:
                pos = redaction.get('position', {})
                x = pos.get('x', 0)
                y = pos.get('y', 0)
                w = pos.get('width', 0)
                h = pos.get('height', 0)
                
                if x > 0 and y > 0 and w > 0 and h > 0:
                    # Use redaction-specific type if provided, otherwise use default
                    redaction_type_specific = redaction.get('redaction_type', redaction_type)
                    
                    # Choose style based on redaction type
                    if redaction_type_specific == 'permanent':
                        # Black box for permanent redaction
                        cv2.rectangle(img_cv, (x, y), (x + w, y + h), (0, 0, 0), -1)
                        # Add thin white border to make the box more visible
                        cv2.rectangle(img_cv, (x, y), (x + w, y + h), (255, 255, 255), 1)
                    else:
                        # Yellow box for temporary redaction
                        cv2.rectangle(img_cv, (x, y), (x + w, y + h), (0, 255, 255), -1)
                        # Add thin black border
                        cv2.rectangle(img_cv, (x, y), (x + w, y + h), (0, 0, 0), 1)
            
            cv2.imwrite(output_path, img_cv)
            
        # For template-based redactions (common fields in known document types)
        elif document_type in ['aadhar', 'aadhaar', 'pan', 'passport']:
            permanent_fields = []
            temporary_fields = []
            
            # Get fields to redact from document type
            doc_fields = {
                'aadhaar': ['name', 'aadhaar_number', 'dob', 'address', 'parent_name'],
                'aadhar': ['name', 'aadhaar_number', 'dob', 'address', 'parent_name'],
                'pan': ['name', 'pan_number', 'dob', 'father_name'],
                'passport': ['name', 'passport_number', 'dob', 'nationality', 'place_of_birth']
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
                border_color = (255, 255, 255)  # White border
            else:
                if redact_method == 'brush':
                    # Red for temporary brush
                    color = (0, 0, 255)  # BGR format
                    border_color = (255, 255, 255)  # White border
                else:
                    # Yellow for temporary select
                    color = (0, 255, 255)  # BGR format - Yellow
                    border_color = (0, 0, 0)  # Black border
                
            # Apply rectangle with the chosen color
            cv2.rectangle(img, (x, y), (x + w, y + h), color, -1)
            # Add border for visibility
            cv2.rectangle(img, (x, y), (x + w, y + h), border_color, 1)
        
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

def apply_pdf_redactions_text_based(file_path, output_path, redactions, document_type='unknown', language='eng'):
    """Process PDF redaction based on selected text fields"""
    pdf_document = fitz.open(file_path)
    
    try:
        for redaction in redactions:
            page_num = redaction.get('page', 0)
            redaction_type = redaction.get('redaction_type', 'temporary')
            
            if page_num < pdf_document.page_count:
                page = pdf_document.load_page(page_num)
                
                # Get position from the field
                pos = redaction.get('position', {})
                if pos and all(k in pos for k in ['x', 'y', 'width', 'height']):
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
                        # Temporary redaction - yellow highlight
                        page.draw_rect(rect, color=(1, 0.9, 0), fill=(1, 0.9, 0, 0.7))
                        # Add text label for better identification
                        field_text = redaction.get('text', '')[:20] + '...' if len(redaction.get('text', '')) > 20 else redaction.get('text', '')
                        page.insert_text((rect.x0, rect.y0 - 5), f"REDACTED: {field_text}", fontsize=8, color=(0, 0, 0))
        
        pdf_document.save(output_path)
        print(f"Text-based PDF redaction completed: {len(redactions)} fields redacted")
        
    except Exception as e:
        print(f"Error in text-based PDF redaction: {e}")
        # Fallback: copy original file
        pdf_document.save(output_path)
    finally:
        pdf_document.close()

def apply_image_redactions_text_based(file_path, output_path, redactions, document_type='unknown', language='eng'):
    """Process image redaction based on selected text fields"""
    try:
        img_cv = cv2.imread(file_path)
        if img_cv is None:
            raise FileNotFoundError(f"Cannot read image: {file_path}")
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        
        for redaction in redactions:
            pos = redaction.get('position', {})
            if pos and all(k in pos for k in ['x', 'y', 'width', 'height']):
                x = int(pos.get('x', 0))
                y = int(pos.get('y', 0))
                w = int(pos.get('width', 0))
                h = int(pos.get('height', 0))
                
                if x > 0 and y > 0 and w > 0 and h > 0:
                    redaction_type = redaction.get('redaction_type', 'temporary')
                    
                    if redaction_type == 'permanent':
                        # Black box for permanent redaction
                        cv2.rectangle(img_cv, (x, y), (x + w, y + h), (0, 0, 0), -1)
                        # White border for visibility
                        cv2.rectangle(img_cv, (x, y), (x + w, y + h), (255, 255, 255), 2)
                        # Add "REDACTED" text
                        cv2.putText(img_cv, "REDACTED", (x + 5, y + h//2), font, font_scale, (255, 255, 255), 1)
                    else:
                        # Yellow box for temporary redaction
                        cv2.rectangle(img_cv, (x, y), (x + w, y + h), (0, 255, 255), -1)
                        # Black border for visibility
                        cv2.rectangle(img_cv, (x, y), (x + w, y + h), (0, 0, 0), 2)
                        # Add field type label
                        field_text = redaction.get('text', '')[:15] + '...' if len(redaction.get('text', '')) > 15 else redaction.get('text', '')
                        cv2.putText(img_cv, f"TEMP: {field_text}", (x + 5, y + h//2), font, font_scale, (0, 0, 0), 1)
        
        cv2.imwrite(output_path, img_cv)
        print(f"Text-based image redaction completed: {len(redactions)} fields redacted")
        
    except Exception as e:
        print(f"Error in text-based image redaction: {str(e)}")
        # Fallback: copy original file
        import shutil
        shutil.copy2(file_path, output_path)

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
    file_path = os.path.join(PROCESSED_FOLDER, file_id)
    
    # First try the processed folder
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    
    # If not found in processed, try the uploads folder
    file_path = os.path.join(UPLOAD_FOLDER, file_id)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    
    return jsonify({'error': 'File not found'}), 404

@app.route('/api/redact-by-text', methods=['POST'])
def redact_by_text():
    """
    API endpoint to redact text by typing what to redact.
    Users can type the exact text they want to redact instead of drawing.
    
    Expected JSON input:
    {
        "file_id": "unique_file_id.ext",
        "text_to_redact": [
            {
                "text": "exact text to find and redact",
                "redaction_type": "permanent|temporary",
                "case_sensitive": true|false
            }
        ],
        "document_type": "aadhar|pan|passport|unknown",
        "language": "eng|tam|hin|etc"
    }
    
    Returns JSON with redacted file information.
    """
    try:
        data = request.json
        file_id = data.get('file_id')
        text_to_redact = data.get('text_to_redact', [])
        document_type = data.get('document_type', 'unknown')
        language = data.get('language', 'eng')
        
        if not file_id:
            return jsonify({'error': 'No file_id provided'}), 400
        
        if not text_to_redact:
            return jsonify({'error': 'No text specified for redaction'}), 400
        
        file_path = os.path.join(UPLOAD_FOLDER, file_id)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        file_extension = os.path.splitext(file_id)[1].lower()
        output_path = os.path.join(PROCESSED_FOLDER, f"redacted_{file_id}")
        
        # Apply text-based redactions
        if file_extension == '.pdf':
            success_count = apply_pdf_text_redactions(file_path, output_path, text_to_redact, language)
        else:
            success_count = apply_image_text_redactions(file_path, output_path, text_to_redact, language)
        
        return jsonify({
            'redacted_file_id': f"redacted_{file_id}",
            'total_redactions_requested': len(text_to_redact),
            'successful_redactions': success_count,
            'redaction_method': 'manual_text_typing'
        })
        
    except Exception as e:
        print(f"Error in text-based redaction: {str(e)}")
        return jsonify({'error': f'Text-based redaction failed: {str(e)}'}), 500
    """
    API endpoint to extract all text fields from a document for manual selection.
    This replaces the manual sketching approach with text-based field selection.
    
    Expected JSON input:
    {
        "file_id": "unique_file_id.ext",
        "document_type": "aadhar|pan|passport|unknown",
        "language": "eng|tam|hin|etc"
    }
    
    Returns JSON with all detected text fields that users can select for redaction.
    """
    try:
        data = request.json
        file_id = data.get('file_id')
        document_type = data.get('document_type', 'unknown')
        language = data.get('language', 'eng')
        
        if not file_id:
            return jsonify({'error': 'No file_id provided'}), 400
        
        file_path = os.path.join(UPLOAD_FOLDER, file_id)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        file_extension = os.path.splitext(file_id)[1].lower()
        
        # Extract text fields from the document
        if file_extension == '.pdf':
            text_fields = extract_from_pdf(file_path, language)
        elif file_extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
            text_fields = extract_from_image(file_path, language)
        else:
            return jsonify({'error': 'Unsupported file type'}), 400
        
        # Categorize fields by likely content type for better organization
        categorized_fields = {
            'names': [],
            'numbers': [],
            'addresses': [],
            'dates': [],
            'other': []
        }
        
        for field in text_fields:
            text = field.get('text', '').strip()
            if not text:
                continue
                
            # Simple categorization based on content
            if re.search(r'\b\d{4}\s?\d{4}\s?\d{4}\b', text):  # Aadhar number pattern
                field['suggested_category'] = 'ID Number'
                categorized_fields['numbers'].append(field)
            elif re.search(r'\b[A-Z]{5}\d{4}[A-Z]\b', text):  # PAN pattern
                field['suggested_category'] = 'ID Number'
                categorized_fields['numbers'].append(field)
            elif re.search(r'\b\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}\b', text):  # Date pattern
                field['suggested_category'] = 'Date'
                categorized_fields['dates'].append(field)
            elif re.search(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', text):  # Name pattern
                field['suggested_category'] = 'Name'
                categorized_fields['names'].append(field)
            elif len(text) > 20 and (',' in text or 'road' in text.lower() or 'street' in text.lower()):  # Address pattern
                field['suggested_category'] = 'Address'
                categorized_fields['addresses'].append(field)
            else:
                field['suggested_category'] = 'Other'
                categorized_fields['other'].append(field)
        
        return jsonify({
            'file_id': file_id,
            'document_type': document_type,
            'language': language,
            'total_fields': len(text_fields),
            'categorized_fields': categorized_fields,
            'all_fields': text_fields
        })
        
    except Exception as e:
        print(f"Error extracting text fields: {str(e)}")
        return jsonify({'error': f'Text field extraction failed: {str(e)}'}), 500

@app.route('/api/redact-selected-fields', methods=['POST'])
def redact_selected_fields():
    """
    API endpoint to redact selected text fields.
    This replaces the coordinate-based redaction with field-based redaction.
    
    Expected JSON input:
    {
        "file_id": "unique_file_id.ext",
        "selected_fields": [
            {
                "id": "field_id",
                "text": "field_text",
                "redaction_type": "permanent|temporary",
                "position": {"x": 0, "y": 0, "width": 0, "height": 0}
            }
        ],
        "document_type": "aadhar|pan|passport|unknown",
        "language": "eng|tam|hin|etc"
    }
    
    Returns JSON with redacted file information.
    """
    try:
        data = request.json
        file_id = data.get('file_id')
        selected_fields = data.get('selected_fields', [])
        document_type = data.get('document_type', 'unknown')
        language = data.get('language', 'eng')
        
        if not file_id:
            return jsonify({'error': 'No file_id provided'}), 400
        
        if not selected_fields:
            return jsonify({'error': 'No fields selected for redaction'}), 400
        
        file_path = os.path.join(UPLOAD_FOLDER, file_id)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        file_extension = os.path.splitext(file_id)[1].lower()
        output_path = os.path.join(PROCESSED_FOLDER, f"redacted_{file_id}")
        
        # Convert selected fields to redaction format
        redactions = []
        for field in selected_fields:
            redaction = {
                'field_id': field.get('id'),
                'text': field.get('text', ''),
                'redaction_type': field.get('redaction_type', 'temporary'),
                'method': 'select',  # Text-based selection
                'position': field.get('position', {}),
                'page': field.get('page', 0)
            }
            redactions.append(redaction)
        
        # Apply redactions
        if file_extension == '.pdf':
            apply_pdf_redactions_text_based(file_path, output_path, redactions, document_type, language)
        else:
            apply_image_redactions_text_based(file_path, output_path, redactions, document_type, language)
        
        return jsonify({
            'redacted_file_id': f"redacted_{file_id}",
            'total_redactions': len(redactions),
            'redaction_method': 'text_based_selection'
        })
        
    except Exception as e:
        print(f"Error in text-based redaction: {str(e)}")
        return jsonify({'error': f'Text-based redaction failed: {str(e)}'}), 500

@app.route('/api/analyze-document', methods=['POST'])
def analyze_document():
    """
    API endpoint to analyze documents using AI for identifying sensitive information.
    This is now used primarily for automatic detection, while manual selection uses get-text-fields.
    
    Expected JSON input:
    {
        "file_id": "unique_file_id.ext",
        "extracted_text": "Text from the document (optional)",
        "data_fields": [{ "id": "...", "text": "...", ... }] (optional)
    }
    
    Returns JSON with identified sensitive fields.
    """
    try:
        data = request.json
        file_id = data.get('file_id')
        
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
                enhanced_fields = enhance_document_fields(data_fields, "unknown")
                
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
        sensitive_fields = analyze_document_text(extracted_text, "unknown")
        
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
