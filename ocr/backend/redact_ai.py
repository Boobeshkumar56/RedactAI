import argparse
import re
import math
from typing import List, Tuple, Dict, Any
import sys
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Dependencies with Fallback ---
try:
    import pytesseract
    from pytesseract import Output
    from PIL import Image
    import cv2
    import numpy as np
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False
    logger.error("Required libraries (pytesseract, OpenCV, Pillow, numpy) not found. Please install them.")
    sys.exit(1)

# --- Global Configurations ---
TEMPLATES = {
    "aadhaar": {
        "name": {'x': 0.12, 'y': 0.22, 'w': 0.6, 'h': 0.08, 'label': 'Name'},
        "aadhaar_number": {'x': 0.12, 'y': 0.34, 'w': 0.5, 'h': 0.08, 'label': 'Aadhaar Number'},
        "address": {'x': 0.12, 'y': 0.46, 'w': 0.7, 'h': 0.12, 'label': 'Address'},
        "dob": {'x': 0.12, 'y': 0.28, 'w': 0.4, 'h': 0.07, 'label': 'Date of Birth'},
    },
    # Make sure aadhar (alternative spelling) has the same template as aadhaar
    "aadhar": {
        "name": {'x': 0.12, 'y': 0.22, 'w': 0.6, 'h': 0.08, 'label': 'Name'},
        "aadhaar_number": {'x': 0.12, 'y': 0.34, 'w': 0.5, 'h': 0.08, 'label': 'Aadhaar Number'},
        "address": {'x': 0.12, 'y': 0.46, 'w': 0.7, 'h': 0.12, 'label': 'Address'},
        "dob": {'x': 0.12, 'y': 0.28, 'w': 0.4, 'h': 0.07, 'label': 'Date of Birth'},
    },
    "pan": {
        "pan_number": {'x': 0.08, 'y': 0.34, 'w': 0.5, 'h': 0.09, 'label': 'PAN'},
        "name": {'x': 0.08, 'y': 0.2, 'w': 0.7, 'h': 0.09, 'label': 'Name'},
        "dob": {'x': 0.08, 'y': 0.26, 'w': 0.5, 'h': 0.08, 'label': 'Date of Birth'},
    },
    "passport": {
        "name": {'x': 0.12, 'y': 0.18, 'w': 0.6, 'h': 0.07, 'label': 'Name'},
        "passport_number": {'x': 0.12, 'y': 0.28, 'w': 0.45, 'h': 0.07, 'label': 'Passport Number'},
        "nationality": {'x': 0.12, 'y': 0.36, 'w': 0.5, 'h': 0.06, 'label': 'Nationality'},
        "dob": {'x': 0.12, 'y': 0.42, 'w': 0.4, 'h': 0.06, 'label': 'Date of Birth'},
    }
}

# Define language-specific patterns and keywords
LANGUAGE_CONFIGS = {
    # English
    "eng": {
        "name_keywords": {"name", "candidate name", "student name", "holder", "cardholder", "full name"},
        "address_keywords": {"address", "residential", "residence", "permanent", "house", "street", "village", "city", "state", "pincode", "pin code"},
        "register_keywords": {"register", "regno", "reg.", "reg", "register no", "register number", "reg number", "reg num"}
    },
    # Tamil
    "tam": {
        "name_keywords": {"பெயர்", "முழுப்பெயர்", "மாணவர் பெயர்", "வைத்திருப்பவர் பெயர்"},
        "address_keywords": {"முகவரி", "வீட்டு முகவரி", "தொடர்பு முகவரி", "நிரந்தர முகவரி", "வீடு", "தெரு", "ஊர்", "மாவட்டம்", "மாநிலம்", "அஞ்சல் குறியீடு"},
        "register_keywords": {"பதிவு எண்", "பதிவெண்", "தொடர் எண்"}
    },
    # Kannada
    "kan": {
        "name_keywords": {"ಹೆಸರು", "ಪೂರ್ಣ ಹೆಸರು", "ವಿದ್ಯಾರ್ಥಿಯ ಹೆಸರು", "ಕಾರ್ಡ್ ಹೊಂದಿರುವವರ ಹೆಸರು"},
        "address_keywords": {"ವಿಳಾಸ", "ನಿವಾಸ", "ಶಾಶ್ವತ ವಿಳಾಸ", "ಮನೆ", "ರಸ್ತೆ", "ಗ್ರಾಮ", "ನಗರ", "ಜಿಲ್ಲೆ", "ರಾಜ್ಯ", "ಪಿನ್ ಕೋಡ್"},
        "register_keywords": {"ನೋಂದಣಿ ಸಂಖ್ಯೆ", "ರಿಜಿಸ್ಟರ್ ಸಂಖ್ಯೆ", "ಕ್ರಮ ಸಂಖ್ಯೆ"}
    },
    # Hindi
    "hin": {
        "name_keywords": {"नाम", "पूरा नाम", "छात्र का नाम", "कार्डधारक का नाम"},
        "address_keywords": {"पता", "निवास स्थान", "स्थायी पता", "घर", "मार्ग", "गाँव", "शहर", "जिला", "राज्य", "पिन कोड"},
        "register_keywords": {"पंजीकरण संख्या", "रजिस्टर नंबर", "क्रम संख्या"}
    },
    # Telugu
    "tel": {
        "name_keywords": {"పేరు", "పూర్తి పేరు", "విద్యార్థి పేరు", "కార్డు హోల్డర్ పేరు"},
        "address_keywords": {"చిరునామా", "నివాస చిరునామా", "స్థిర చిరునామా", "ఇల్లు", "రోడ్డు", "గ్రామం", "నగరం", "జిల్లా", "రాష్ట్రం", "పిన్ కోడ్"},
        "register_keywords": {"నమోదు సంఖ్య", "రిజిస్టర్ నంబర్", "క్రమ సంఖ్య"}
    },
    # Malayalam
    "mal": {
        "name_keywords": {"പേര്", "മുഴുവൻ പേര്", "വിദ്യാർത്ഥിയുടെ പേര്", "കാർഡ് ഉടമയുടെ പേര്"},
        "address_keywords": {"വിലാസം", "താമസ വിലാസം", "സ്ഥിര വിലാസം", "വീട്", "തെരുവ്", "ഗ്രാമം", "നഗരം", "ജില്ല", "സംസ്ഥാനം", "പിൻ കോഡ്"},
        "register_keywords": {"രജിസ്ട്രേഷൻ നമ്പർ", "രജിസ്റ്റർ നമ്പർ", "ക്രമ നമ്പർ"}
    }
}

# Common patterns that work across languages
AADHAAR_RE = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
DATE_RE = re.compile(r"\b(?:\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}|(?:\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}))\b")
# Default English keywords for backward compatibility
NAME_KWS = LANGUAGE_CONFIGS["eng"]["name_keywords"]
REGISTER_KWS = LANGUAGE_CONFIGS["eng"]["register_keywords"]

# Keywords that should NOT be redacted (official headers, etc.)
NON_SENSITIVE_KEYWORDS = {
    # English
    "government of india", "govt of india", "government", "unique identification", "uidai", "issued by", "verify", 
    "signature", "male", "female", "gender", "help", "toll free", "aadhaar", "identification", "authority",
    # Hindi
    "भारत सरकार", "सरकार", "पहचान", "प्राधिकरण", "जारी किया गया", "सत्यापित", "पुरुष", "महिला", "लिंग", "मदद", "टोल फ्री",
    # Tamil
    "இந்திய அரசு", "அரசு", "அடையாளம்", "ஆணையம்", "வழங்கப்பட்டது", "சரிபார்க்கவும்", "ஆண்", "பெண்", "பாலினம்", "உதவி", "கட்டணமில்லா",
    # Kannada
    "ಭಾರತ ಸರ್ಕಾರ", "ಸರ್ಕಾರ", "ಗುರುತಿನ", "ಪ್ರಾಧಿಕಾರ", "ನೀಡಿದ", "ಪರಿಶೀಲಿಸಿ", "ಪುರುಷ", "ಮಹಿಳೆ", "ಲಿಂಗ", "ಸಹಾಯ", "ಟೋಲ್ ಫ್ರೀ",
    # Telugu
    "భారత ప్రభుత్వం", "ప్రభుత్వం", "గుర్తింపు", "అథారిటీ", "జారీ చేయబడింది", "ధృవీకరించండి", "పురుషుడు", "స్త్రీ", "లింగం", "సహాయం", "టోల్ ఫ్రీ",
    # Malayalam
    "ഇന്ത്യ സർക്കാർ", "സർക്കാർ", "തിരിച്ചറിയൽ", "അതോറിറ്റി", "നൽകിയത്", "പരിശോധിക്കുക", "പുരുഷൻ", "സ്ത്രീ", "ലിംഗം", "സഹായം", "ടോൾ ഫ്രീ"
}

# --- Image Preprocessing Functions ---
def _auto_rotate(gray: np.ndarray) -> np.ndarray:
    """Estimate small skew and deskew using Hough lines."""
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=200)
    if lines is None:
        return gray
    angles = []
    for rho, theta in lines[:, 0]:
        angle = (theta - np.pi/2) * 180 / np.pi
        if -20 < angle < 20:
            angles.append(angle)
    if not angles:
        return gray
    median_angle = np.median(angles)
    h, w = gray.shape[:2]
    M = cv2.getRotationMatrix2D((w//2, h//2), median_angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

def preprocess_image_for_ocr(image_path: str, debug: bool = False) -> Tuple[np.ndarray, np.ndarray]:
    """Returns (original_color_bgr, processed_gray_for_ocr)"""
    orig = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if orig is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")
    
    scale = 1.5 if max(orig.shape[:2]) < 1600 else 1.0
    if scale != 1.0:
        orig = cv2.resize(orig, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(orig, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 60, 60)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    
    _, bin_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 31, 8)
    def textiness(img):
        cnts, _ = cv2.findContours(255 - img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        sizes = [cv2.contourArea(c) for c in cnts]
        return sum(1 for a in sizes if 20 < a < 10000)
    proc = bin_otsu if textiness(bin_otsu) >= textiness(adaptive) else adaptive
    
    proc = _auto_rotate(proc)
    proc = cv2.medianBlur(proc, 3)
    if debug:
        cv2.imwrite("debug_preprocessed.png", proc)
    return orig, proc

# --- OCR & Detection Functions ---
def _ocr_with_boxes(img_gray_or_bin: np.ndarray, lang: str) -> Dict[str, List[Any]]:
    config = "--oem 3 --psm 6"
    data = pytesseract.image_to_data(img_gray_or_bin, lang=lang, config=config, output_type=Output.DICT)
    return data

def _merge_boxes(boxes: List[Tuple[int, int, int, int]]) -> Tuple[int, int, int, int]:
    if not boxes:
        return (0, 0, 0, 0)
    xs = [x for x, y, w, h in boxes]
    ys = [y for x, y, w, h in boxes]
    xe = [x + w for x, y, w, h in boxes]
    ye = [y + h for x, y, w, h in boxes]
    return (min(xs), min(ys), max(xe) - min(xs), max(ye) - min(ys))

def _words_after_keyword(i: int, data: Dict[str, List[Any]], max_words: int = 4) -> Tuple[str, List[int]]:
    line = data['line_num'][i]
    indices = [j for j in range(i + 1, len(data['text'])) if data['line_num'][j] == line and data['text'][j].strip()]
    take = indices[:max_words]
    text = " ".join(data['text'][j] for j in take).strip()
    return text, take

def detect_entities_from_ocr(data: Dict[str, List[Any]], requested_fields: set, debug: bool = False, lang: str = "eng"):
    hits: Dict[str, List[Tuple[int, int, int, int]]] = {f: [] for f in requested_fields}
    words = [(w or "").strip() for w in data['text']]
    
    # Get language-specific keywords
    # Parse language code - if multi-language like "eng+tam", use first language
    primary_lang = lang.split('+')[0] if '+' in lang else lang
    # Fallback to English if language not in our configs
    if primary_lang not in LANGUAGE_CONFIGS:
        if debug:
            print(f"[DEBUG] Language '{primary_lang}' not in configs, using English as fallback")
        primary_lang = "eng"
        
    name_keywords = LANGUAGE_CONFIGS[primary_lang]["name_keywords"]
    address_keywords = LANGUAGE_CONFIGS[primary_lang]["address_keywords"]
    register_keywords = LANGUAGE_CONFIGS[primary_lang]["register_keywords"]
    
    if debug:
        print(f"[DEBUG] Using language: {primary_lang}")
        print(f"[DEBUG] Name keywords: {name_keywords}")
    
    # Pass 1: regex matches
    full_text = " ".join(words)
    starts = []
    text_builder = []
    for idx, w in enumerate(words):
        if not w:
            continue
        starts.append((len(" ".join(text_builder)), idx))
        text_builder.append(w)
    full_text = " ".join(text_builder)
    
    # Check if text contains non-sensitive terms that should be excluded
    def is_non_sensitive(text):
        text = text.lower()
        for term in NON_SENSITIVE_KEYWORDS:
            if term in text:
                return True
        return False

    # Detect Aadhaar numbers 
    if "aadhaar_number" in requested_fields:
        # More aggressive pattern to catch Aadhaar numbers even with OCR errors
        for m in AADHAAR_RE.finditer(full_text):
            token_idxs = []
            m_start, m_end = m.span()
            for start_char, idx in starts:
                w = (words[idx] or "").strip()
                end_char = start_char + len(w)
                if not (end_char < m_start or start_char > m_end):
                    token_idxs.append(idx)
            if token_idxs:
                boxes = [(data['left'][i], data['top'][i], data['width'][i], data['height'][i]) for i in token_idxs]
                hits["aadhaar_number"].append(_merge_boxes(boxes))
                
        # Also check for keywords like "Aadhaar", "आधार", etc. followed by digits
        aadhaar_keywords = {
            "aadhar", "aadhaar", "आधार", "ஆதார்", "ಆಧಾರ್", "ആധാർ", "ఆధార్"
        }
        for i, w in enumerate(lowered):
            if any(kw in w for kw in aadhaar_keywords):
                # Look for digits in next few words
                _, idxs = _words_after_keyword(i, data, max_words=4)
                if idxs:
                    # Look for digit patterns in those words
                    id_text = "".join([data['text'][j] for j in idxs])
                    if re.search(r'\d{4}', id_text):  # Even partial match is worth checking
                        boxes = [(data['left'][j], data['top'][j], data['width'][j], data['height'][j]) for j in idxs]
                        hits["aadhaar_number"].append(_merge_boxes(boxes))

    # Detect PAN numbers
    if "pan_number" in requested_fields:
        for m in PAN_RE.finditer(full_text):
            token_idxs = []
            m_start, m_end = m.span()
            for start_char, idx in starts:
                w = (words[idx] or "").strip()
                end_char = start_char + len(w)
                if not (end_char < m_start or start_char > m_end):
                    token_idxs.append(idx)
            if token_idxs:
                boxes = [(data['left'][i], data['top'][i], data['width'][i], data['height'][i]) for i in token_idxs]
                hits["pan_number"].append(_merge_boxes(boxes))
    
    # Detect dates (including DOB)
    if "dob" in requested_fields:
        for m in DATE_RE.finditer(full_text):
            token_idxs = []
            m_start, m_end = m.span()
            for start_char, idx in starts:
                w = (words[idx] or "").strip()
                end_char = start_char + len(w)
                if not (end_char < m_start or start_char > m_end):
                    token_idxs.append(idx)
            if token_idxs:
                boxes = [(data['left'][i], data['top'][i], data['width'][i], data['height'][i]) for i in token_idxs]
                hits["dob"].append(_merge_boxes(boxes))

    # Pass 2: keyword spans
    lowered = [(w or "").strip().lower() for w in data['text']]
    
    # Detect names
    if "name" in requested_fields:
        for i, w in enumerate(lowered):
            if any(kw in w for kw in name_keywords):
                _, idxs = _words_after_keyword(i, data, max_words=4)
                if idxs:
                    # Skip if the detected text is in our non-sensitive list
                    text = " ".join([data['text'][j] for j in idxs]).lower()
                    if not is_non_sensitive(text):
                        boxes = [(data['left'][j], data['top'][j], data['width'][j], data['height'][j]) for j in idxs]
                        hits["name"].append(_merge_boxes(boxes))
    
    # Detect address
    if "address" in requested_fields:
        for i, w in enumerate(lowered):
            if any(kw in w for kw in address_keywords):
                _, idxs = _words_after_keyword(i, data, max_words=10)  # Addresses are longer
                if idxs:
                    # Skip if the detected text is in our non-sensitive list
                    text = " ".join([data['text'][j] for j in idxs]).lower()
                    if not is_non_sensitive(text):
                        boxes = [(data['left'][j], data['top'][j], data['width'][j], data['height'][j]) for j in idxs]
                        hits["address"].append(_merge_boxes(boxes))

    # Detect registration numbers
    if "register_number" in requested_fields:
        for i, w in enumerate(lowered):
            if any(kw in w for kw in register_keywords):
                _, idxs = _words_after_keyword(i, data, max_words=2)
                if idxs:
                    # Skip if the detected text is in our non-sensitive list
                    text = " ".join([data['text'][j] for j in idxs]).lower()
                    if not is_non_sensitive(text):
                        boxes = [(data['left'][j], data['top'][j], data['width'][j], data['height'][j]) for j in idxs]
                        hits["register_number"].append(_merge_boxes(boxes))

    # Deduplicate
    for k in list(hits.keys()):
        uniq = []
        seen = set()
        for (x, y, w, h) in hits[k]:
            key = (x // 2, y // 2, w // 2, h // 2)
            if key not in seen:
                seen.add(key)
                uniq.append((x, y, w, h))
        hits[k] = uniq
    
    if debug:
        print("[DEBUG] Detected fields:")
        for field, boxes in hits.items():
            print(f"  {field}: {len(boxes)} boxes found")
    
    return hits

def draw_redactions(color_bgr: np.ndarray, boxes: List[Tuple[int, int, int, int]], style: str = "black"):
    for (x, y, w, h) in boxes:
        if style == "blur":
            roi = color_bgr[y:y + h, x:x + w]
            if roi.size == 0: continue
            roi = cv2.GaussianBlur(roi, (25, 25), 0)
            color_bgr[y:y + h, x:x + w] = roi
        elif style == "pixel":
            roi = color_bgr[y:y + h, x:x + w]
            if roi.size == 0: continue
            ph, pw = max(6, h // 12), max(6, w // 12)
            roi_small = cv2.resize(roi, (pw, ph), interpolation=cv2.INTER_LINEAR)
            roi_pix = cv2.resize(roi_small, (w, h), interpolation=cv2.INTER_NEAREST)
            color_bgr[y:y + h, x:x + w] = roi_pix
        elif style == "yellow":
            # Yellow highlight for temporary redaction
            cv2.rectangle(color_bgr, (x, y), (x + w, y + h), (0, 255, 255), thickness=-1)
        elif style == "red":
            # Red highlight for brush redaction
            cv2.rectangle(color_bgr, (x, y), (x + w, y + h), (0, 0, 255), thickness=-1)
        else:
            # Black by default for permanent redaction
            cv2.rectangle(color_bgr, (x, y), (x + w, y + h), (0, 0, 0), thickness=-1)

# --- Main Redaction Function ---
def redact_image(image_path: str, doc_type: str = "unknown",
                 permanent_fields: List[str] = None, temporary_fields: List[str] = None,
                 lang: str = "eng", debug: bool = False, style: str = "black") -> Image.Image:
    if permanent_fields is None: permanent_fields = []
    if temporary_fields is None: temporary_fields = []
    
    color_bgr, ocr_img = preprocess_image_for_ocr(image_path, debug=debug)
    h, w = color_bgr.shape[:2]
    req_fields = set([f.lower() for f in (permanent_fields + temporary_fields)])
    
    # Check if document type is Aadhar with alternate spelling
    if doc_type.lower() in ['aadhar', 'aadhaar']:
        doc_type_normalized = 'aadhaar'  # Normalize to one spelling
        # Always include Aadhaar number in requested fields for Aadhar cards
        req_fields.add('aadhaar_number')
    else:
        doc_type_normalized = doc_type.lower()

    # First try to detect fields using OCR for all document types
    data = _ocr_with_boxes(ocr_img, lang=lang)
    if debug:
        extracted = " ".join([t for t in data['text'] if t and t.strip()])
        print(f"\n[DEBUG] Raw Extracted Text ({lang}):\n", extracted, "\n")
        print(f"[DEBUG] Document type: {doc_type_normalized}")
        print(f"[DEBUG] Requested fields: {req_fields}")
    
    boxes_by_field = detect_entities_from_ocr(data, req_fields, debug=debug, lang=lang)
    
    # Process detected fields first
    fields_redacted = set()
    for field, boxes in boxes_by_field.items():
        if boxes:  # Only if we found boxes for this field
            redaction_style = "black" if field in permanent_fields else "yellow"
            draw_redactions(color_bgr, boxes, style=redaction_style)
            fields_redacted.add(field)
            if debug:
                print(f"[DEBUG] Applied OCR-detected redactions for {field}")
    
    # Fall back to template coordinates for fields that weren't detected
    if doc_type_normalized in TEMPLATES:
        template_fields = TEMPLATES[doc_type_normalized]
        for f in req_fields:
            if f in template_fields and f not in fields_redacted:
                box_norm = template_fields[f]
                x = int(box_norm['x'] * w)
                y = int(box_norm['y'] * h)
                width = int(box_norm['w'] * w)
                height = int(box_norm['h'] * h)
                redaction_style = "black" if f in permanent_fields else "yellow"
                draw_redactions(color_bgr, [(x, y, width, height)], style=redaction_style)
                if debug:
                    print(f"[DEBUG] Applied template-based redactions for {f}")
    
    # Special case for Aadhar cards - make sure aadhaar_number is always redacted
    # This is a fallback in case both OCR and template failed
    if doc_type_normalized == 'aadhaar' and 'aadhaar_number' in req_fields and 'aadhaar_number' not in fields_redacted:
        # Apply a wider redaction area for Aadhar number as a last resort
        center_y = int(h * 0.34)  # Typical location for Aadhar number
        redaction_style = "black" if 'aadhaar_number' in permanent_fields else "yellow"
        draw_redactions(color_bgr, [(int(w * 0.1), center_y, int(w * 0.8), int(h * 0.08))], style=redaction_style)
        if debug:
            print(f"[DEBUG] Applied fallback redaction for aadhaar_number")

    return Image.fromarray(cv2.cvtColor(color_bgr, cv2.COLOR_BGR2RGB))

# --- Function to process custom redactions ---
def apply_custom_redactions(image_path: str, redactions: List[dict], redaction_type: str = "temporary"):
    """Apply custom redactions to an image based on coordinates provided."""
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")
    
    for redaction in redactions:
        pos = redaction.get('position', {})
        x = pos.get('x', 0)
        y = pos.get('y', 0)
        w = pos.get('width', 0)
        h = pos.get('height', 0)
        method = redaction.get('method', 'select')
        
        if x > 0 and y > 0 and w > 0 and h > 0:
            if redaction_type == 'permanent':
                # Black for permanent redaction
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 0), -1)
            else:
                if method == 'brush':
                    # Yellow for temporary brush redaction
                    cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 255), -1)
                else:
                    # Gray for temporary selection redaction
                    cv2.rectangle(img, (x, y), (x + w, y + h), (192, 192, 192), -1)
    
    return img

# --- Command Line Interface (CLI) ---
if __name__ == "__main__":
    if not HAS_DEPENDENCIES:
        sys.exit(1)
        
    parser = argparse.ArgumentParser(
        description="RedactAI - Advanced document redaction\n",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--image", required=True, help="Path to input image")
    parser.add_argument("--doc_type", default="unknown", help="aadhaar | pan | passport | unknown")
    parser.add_argument("--permanent_fields", nargs="*", default=[], help="Fields to redact permanently")
    parser.add_argument("--temporary_fields", nargs="*", default=[], help="Fields to redact temporarily")
    parser.add_argument("--output", default="redacted_output.jpg", help="Output file name")
    parser.add_argument("--lang", default="eng", help="Tesseract language (e.g. eng, eng+hin)")
    parser.add_argument("--style", default="black", choices=["black", "blur", "pixel"], help="Redaction style")
    parser.add_argument("--debug", action="store_true", help="Print OCR text and save debug image")

    args = parser.parse_args()
    
    try:
        img = redact_image(
            image_path=args.image,
            doc_type=args.doc_type,
            permanent_fields=args.permanent_fields,
            temporary_fields=args.temporary_fields,
            lang=args.lang,
            debug=args.debug,
            style=args.style
        )
        img.save(args.output)
        print(f"✅ Redacted image saved to {args.output}")
        if args.debug:
            print("🧪 Saved preprocessing snapshot to debug_preprocessed.png.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)
