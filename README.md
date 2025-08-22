# RedactAI: Advanced Document Redaction System


RedactAI is a powerful document redaction system designed to protect sensitive information in various types of documents. Using advanced OCR technology and AI-assisted detection, RedactAI makes it easy to identify and redact personal information from PDF files and images.

## 🌟 Unique Value Proposition

- **Smart Document Analysis**: Automatically detects sensitive information using AI-powered analysis
- **Multiple Redaction Methods**: Choose between AI-assisted redaction or text-based redaction
- **Customizable Redaction Types**: Apply temporary or permanent redactions based on your needs
- **User-friendly Interface**: Intuitive web interface for easy document processing

## 📋 Features

- **Document Upload**: Support for PDF and image formats (JPG, PNG, TIFF, etc.)
- **OCR Technology**: Extract text from scanned documents and images
- **AI Analysis**: Automatically identify sensitive information like names, addresses, ID numbers
- **Field Selection**: Select specific fields detected by AI for redaction
- **Text-based Redaction**: Type specific text to find and redact across the document
- **Permanent/Temporary Redaction**: Choose between black boxes (permanent) or yellow highlights (temporary)
- **Multi-language Support**: Process documents in multiple Indian languages
- **Downloadable Results**: Download the redacted document in its original format

## Project Structure

```
RedactAI/
├── ocr/
│   ├── backend/
│   │   ├── app.py                # Flask backend server
│   │   └── requirements.txt      # Python dependencies
│   └── frontend/
│       ├── public/               # Static files
│       └── src/                  # React source code
│           ├── components/       # React components
│           │   ├── Header.js     # App header
│           │   ├── UploadPage.js # File upload page
│           │   └── EditorPage.js # Document editor page
│           ├── App.js            # Main App component
│           └── index.js          # Entry point
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Node.js 14+
- Tesseract OCR with language data files

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/Boobeshkumar56/RedactAI.git
cd RedactAI/ocr

# Create and activate virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Run the backend server
cd backend
python app.py
```

### Frontend Setup

```bash
# Navigate to frontend directory
cd ../frontend

# Install dependencies
npm install

# Run the development server
npm start
```

The application should now be accessible at http://localhost:3000

## 📚 API Documentation

RedactAI offers a comprehensive API for document redaction:

### 1. Upload Document

**Endpoint:** `POST /api/upload`

**Content-Type:** `multipart/form-data`

**Request Parameters:**
- `file`: The document file (PDF, JPG, PNG, etc.)
- `language`: Language code ('eng', 'tam', 'hin', 'tel', 'kan', 'mal', or combinations like 'eng+tam')

**Response:**
```json
{
  "file_id": "unique-file-identifier.pdf",
  "original_filename": "original-name.pdf",
  "language": "eng",
  "data_fields": [
    {
      "id": "field-id",
      "text": "Extracted text",
      "page": 0,
      "confidence": 90,
      "position": {
        "x": 100,
        "y": 200,
        "width": 300,
        "height": 50
      }
    }
  ]
}
```

### 2. Apply Redactions

**Endpoint:** `POST /api/redact`

**Content-Type:** `application/json`

**Request Parameters:**

For field selection redaction:
```json
{
  "file_id": "unique-file-identifier.pdf",
  "redactions": [
    {
      "id": "field-id",
      "text": "Text to redact",
      "page": 0,
      "redaction_type": "temporary",
      "position": {
        "x": 100,
        "y": 200,
        "width": 300,
        "height": 50
      }
    }
  ],
  "redaction_type": "temporary",
  "language": "eng"
}
```

For text-based redaction:
```json
{
  "file_id": "unique-file-identifier.pdf",
  "text_to_redact": [
    {
      "text": "John Doe",
      "redaction_type": "permanent",
      "case_sensitive": false
    }
  ],
  "document_type": "unknown",
  "language": "eng"
}
```

**Response:**
```json
{
  "redacted_file_id": "redacted_unique-file-identifier.pdf",
  "total_redactions": 3,
  "redaction_method": "manual_typing"
}
```

### 3. Download Redacted Document

**Endpoint:** `GET /api/download/{file_id}`

**Response:** The redacted document file.

### 4. AI Document Analysis

**Endpoint:** `POST /api/analyze-document`

**Content-Type:** `application/json`

**Request Parameters:**
```json
{
  "file_id": "unique-file-identifier.pdf",
  "language": "eng"
}
```

**Response:**
```json
{
  "sensitive_fields": [
    {
      "id": "ai-field-123",
      "text": "John Doe",
      "category": "Name",
      "ai_confidence": 95,
      "position": {
        "x": 100,
        "y": 200,
        "width": 300,
        "height": 50
      }
    }
  ],
  "analysis_type": "gemini_ai"
}
```



## 🔮 Future Enhancements

1. **Document Type Selection**: Add support for selecting document types to enable template-based redaction for standard documents like Aadhaar cards, PAN cards, and passports.

2. **Manual Sketching Tool**: Implementing a drawing-based redaction tool to allow users to manually mark areas for redaction using a pen or brush tool.

3. **Custom Template Creation**: Allow users to create and save their own templates for repeated document types.

4. **Batch Processing**: Support for uploading and processing multiple documents at once.

5. **Document Classification AI**: Automatically detect document type without user input.

6. **Enhanced Security Features**: Add watermarking, encryption, and audit logging for redacted documents.

7. **Mobile Application**: Develop mobile apps for on-the-go document redaction.

8. **Integration with Cloud Storage**: Direct integration with Google Drive, Dropbox, etc.

9. **Advanced OCR Enhancement**: Implement pre-processing techniques to improve OCR accuracy for low-quality scans.

10. **Browser Extension**: Create a browser extension for quick redaction of online documents.

11. **Enterprise Features**: Role-based access control, organization management, and compliance reporting.

## 🔄 Workflow

1. Upload your document (PDF or image)
2. Choose language for OCR processing
3. Select redaction method:
   - AI Analysis: Automatically detect and select sensitive information
   - Text-based Redaction: Type specific text to find and redact
4. Choose redaction type (temporary or permanent)
5. Apply redactions
6. Download the redacted document

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👥 Contributors

- [Boobeshkumar56](https://github.com/Boobeshkumar56) - Creator and maintainer
