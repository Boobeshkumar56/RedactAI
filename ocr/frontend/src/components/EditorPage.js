import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Document, Page, pdfjs } from 'react-pdf';
import styled from 'styled-components';
import CanvasDraw from 'react-canvas-draw';
import apiClient, { getApiUrl } from '../services/api';

// Import the required PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`;

// Main container with modern design
const EditorContainer = styled.div`
  display: flex;
  height: calc(100vh - 64px);
  background-color: #f0f2f5;
  overflow: hidden;
`;

// Document viewer - left side panel
const DocumentPane = styled.div`
  flex: 3;
  background-color: #fff;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  overflow: auto;
  padding: 20px;
`;

// Controls - right side panel
const ControlPane = styled.div`
  flex: 1;
  min-width: 350px;
  max-width: 400px;
  background-color: #fff;
  box-shadow: -2px 0 10px rgba(0, 0, 0, 0.05);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  z-index: 10;
  padding: 20px;
`;

// Section for grouping related controls
const Section = styled.div`
  margin-bottom: 24px;
  border-bottom: 1px solid #eaeaea;
  padding-bottom: 20px;

  &:last-child {
    border-bottom: none;
  }
`;

// Section headers
const SectionTitle = styled.h3`
  font-size: 16px;
  color: #333;
  margin-bottom: 16px;
  font-weight: 600;
`;

// Tabs for mode selection
const ModeTabs = styled.div`
  display: flex;
  margin-bottom: 16px;
  background: #f5f5f5;
  border-radius: 8px;
  padding: 4px;
`;

const ModeTab = styled.button`
  flex: 1;
  padding: 10px 16px;
  background: ${props => props.active ? '#3f51b5' : 'transparent'};
  color: ${props => props.active ? 'white' : '#555'};
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: ${props => props.active ? '600' : '400'};
  transition: all 0.2s ease;

  &:hover {
    background: ${props => props.active ? '#3f51b5' : '#e0e0e0'};
  }
`;

// Redaction type options
const RedactionOptions = styled.div`
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
`;

const RedactionOption = styled.div`
  flex: 1;
  display: flex;
  align-items: center;
  padding: 12px;
  border: 2px solid ${props => props.selected ? '#bbdefb' : '#e0e0e0'};
  border-radius: 8px;
  background-color: ${props => props.selected ? '#e3f2fd' : 'white'};
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    border-color: #bbdefb;
    background-color: ${props => props.selected ? '#e3f2fd' : '#f5f9ff'};
  }
`;

const ColorIndicator = styled.span`
  display: inline-block;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  margin-right: 10px;
  background-color: ${props => props.color};
  border: 1px solid rgba(0, 0, 0, 0.1);
`;

const OptionLabel = styled.span`
  font-weight: 500;
`;

// Field list styles
const FieldList = styled.div`
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  margin-bottom: 16px;
`;

const FieldItem = styled.div`
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
  background-color: ${props => props.selected ? '#e3f2fd' : 'white'};
  cursor: pointer;
  transition: background-color 0.2s ease;
  display: flex;
  flex-direction: column;

  &:last-child {
    border-bottom: none;
  }

  &:hover {
    background-color: ${props => props.selected ? '#e3f2fd' : '#f5f5f5'};
  }
`;

const FieldName = styled.div`
  font-weight: 500;
  margin-bottom: 4px;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const FieldValue = styled.div`
  font-size: 13px;
  color: #666;
  margin-bottom: 6px;
`;

const FieldControls = styled.div`
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 6px;
  display: ${props => props.visible ? 'flex' : 'none'};
`;

const RedactionTypeButton = styled.button`
  background-color: ${props => props.selected ? (props.permanent ? '#f44336' : '#ffeb3b') : '#e0e0e0'};
  color: ${props => props.selected && props.permanent ? 'white' : 'black'};
  border: none;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  opacity: ${props => props.selected ? 1 : 0.7};

  &:hover {
    opacity: 1;
    background-color: ${props => props.permanent ? '#e53935' : '#fdd835'};
  }
`;

// Summary section
const SummaryItem = styled.div`
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
`;

// Canvas wrapper for drawing
const CanvasWrapper = styled.div`
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: ${props => props.active ? 'auto' : 'none'};
  z-index: ${props => props.active ? 10 : -1};
  background-color: transparent; /* Ensure background is transparent */
  display: flex;
  align-items: center;
  justify-content: center;
`;

// Button styles
const Button = styled.button`
  padding: 12px 16px;
  background-color: ${props => props.primary ? '#3f51b5' : props.danger ? '#f44336' : '#e0e0e0'};
  color: ${props => props.primary || props.danger ? 'white' : '#333'};
  border: none;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  margin-top: 10px;
  transition: background-color 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;

  &:hover {
    background-color: ${props => props.primary ? '#303f9f' : props.danger ? '#d32f2f' : '#bdbdbd'};
  }

  &:disabled {
    background-color: #bdbdbd;
    cursor: not-allowed;
  }
`;

const ButtonGroup = styled.div`
  display: flex;
  flex-direction: column;
  margin-top: auto;
  padding-top: 20px;
  
  ${Button} + ${Button} {
    margin-top: 10px;
  }
`;

// Pagination controls
const PaginationControls = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  margin-top: 20px;
  padding: 10px;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
`;

const PageButton = styled.button`
  padding: 8px 16px;
  background-color: ${props => props.disabled ? '#f5f5f5' : '#3f51b5'};
  color: ${props => props.disabled ? '#bdbdbd' : 'white'};
  border: none;
  border-radius: 4px;
  margin: 0 8px;
  cursor: ${props => props.disabled ? 'not-allowed' : 'pointer'};
  transition: all 0.2s ease;

  &:hover {
    background-color: ${props => props.disabled ? '#f5f5f5' : '#303f9f'};
  }
`;

const PageInfo = styled.div`
  padding: 0 16px;
  font-size: 14px;
  font-weight: 500;
`;

// Message containers
const ErrorMessage = styled.div`
  padding: 12px 16px;
  margin: 12px 0;
  background-color: #ffebee;
  border-left: 4px solid #f44336;
  color: #b71c1c;
  border-radius: 4px;
`;

const SuccessMessage = styled.div`
  padding: 12px 16px;
  margin: 12px 0;
  background-color: #e8f5e9;
  border-left: 4px solid #4caf50;
  color: #1b5e20;
  border-radius: 4px;
`;

const InfoMessage = styled.div`
  padding: 12px 16px;
  margin: 12px 0;
  background-color: #e3f2fd;
  border-left: 4px solid #2196f3;
  color: #0d47a1;
  border-radius: 4px;
`;

const LoadingSpinner = styled.div`
  border: 3px solid rgba(0, 0, 0, 0.1);
  border-radius: 50%;
  border-top: 3px solid #3f51b5;
  width: 20px;
  height: 20px;
  margin-right: 10px;
  animation: spin 1s linear infinite;

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
`;

// Empty state
const EmptyState = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 20px;
  text-align: center;
  color: #757575;
`;

function EditorPage({ uploadedFile }) {
  const navigate = useNavigate();
  
  // Document state
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [pageWidth, setPageWidth] = useState(0);
  const [pageHeight, setPageHeight] = useState(0);
  const [uploadedFileState, setUploadedFileState] = useState(uploadedFile || null);
  
  // UI state
  const [activeMode, setActiveMode] = useState('select'); // 'select' or 'brush'
  const [redactionType, setRedactionType] = useState('temporary'); // 'temporary' or 'permanent'
  const [selectedFields, setSelectedFields] = useState([]);
  const [redactions, setRedactions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showPreview, setShowPreview] = useState(false);
  const [previewUrl, setPreviewUrl] = useState('');
  
  // AI analysis state
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [aiSuggestedFields, setAiSuggestedFields] = useState([]);
  const [aiAnalysisComplete, setAiAnalysisComplete] = useState(false);
  
  // Brush settings
  const [brushSize, setBrushSize] = useState(8); // Default brush size
  
  // Refs
  const canvasRef = useRef(null);
  const documentRef = useRef(null);
  
  // Get brush color based on redaction type
  const getBrushColor = () => {
    return redactionType === 'temporary' ? '#FFFF00' : '#FF0000';
  };
  
  // Load document from localStorage if not provided as prop
  useEffect(() => {
    if (!uploadedFile) {
      const savedFileData = localStorage.getItem('uploadedFile');
      if (savedFileData) {
        try {
          const parsedData = JSON.parse(savedFileData);
          setUploadedFileState(parsedData);
        } catch (error) {
          console.error("Error parsing saved file data:", error);
          navigate('/');
        }
      } else {
        navigate('/');
      }
    } else {
      setUploadedFileState(uploadedFile);
    }
  }, [uploadedFile, navigate]);
  
  // Handle document container resizing
  useEffect(() => {
    const handleResize = () => {
      if (documentRef.current) {
        setPageWidth(documentRef.current.clientWidth * 0.85);
      }
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, []);
  
    // Reset canvas when dimensions change
  useEffect(() => {
    if (pageWidth > 0 && pageHeight > 0 && canvasRef.current && activeMode === 'brush') {
      try {
        // Force canvas resize/reset when dimensions change
        canvasRef.current.clear();
        
        // Get document element position
        const documentElement = document.querySelector('.react-pdf__Page');
        if (documentElement) {
          const docRect = documentElement.getBoundingClientRect();
          console.log('Document position:', docRect);
        }
      } catch (error) {
        console.error("Error resetting canvas:", error);
      }
    }
  }, [pageWidth, pageHeight, activeMode]);
  
  // Document loading handlers
  function onDocumentLoadSuccess({ numPages }) {
    setNumPages(numPages);
    setPageNumber(1);
    
    // After document loads, get element position for proper canvas alignment
    setTimeout(() => {
      const documentElement = document.querySelector('.react-pdf__Page');
      if (documentElement) {
        const docRect = documentElement.getBoundingClientRect();
        console.log('Document loaded with dimensions:', docRect);
      }
    }, 500);
  }
  
  // Page navigation
  function handlePreviousPage() {
    setPageNumber(prevPageNumber => Math.max(prevPageNumber - 1, 1));
  }

  function handleNextPage() {
    setPageNumber(prevPageNumber => Math.min(prevPageNumber + 1, numPages));
  }
  
  // Mode switching
  function handleModeChange(mode) {
    setActiveMode(mode);
    if (mode === 'select' && canvasRef.current) {
      try {
        canvasRef.current.clear();
      } catch (error) {
        console.error("Error clearing canvas:", error);
      }
    }
  }
  
  // Redaction type change
  function handleRedactionTypeChange(type) {
    setRedactionType(type);
  }
  
  // Field selection
  function handleFieldSelect(field) {
    if (activeMode === 'select') {
      const isSelected = selectedFields.some(f => f.id === field.id);
      
      if (isSelected) {
        setSelectedFields(selectedFields.filter(f => f.id !== field.id));
      } else {
        setSelectedFields([...selectedFields, {
          ...field,
          method: 'select',
          redaction_type: redactionType // Use the current global redaction type as default
        }]);
      }
    }
  }
  
  // Update redaction type for a specific field
  function handleFieldRedactionTypeChange(fieldId, type) {
    setSelectedFields(
      selectedFields.map(field => 
        field.id === fieldId 
          ? { ...field, redaction_type: type } 
          : field
      )
    );
  }
  
  // Canvas drawing
  function handleCanvasDraw() {
    if (canvasRef.current && activeMode === 'brush' && pageWidth > 0 && pageHeight > 0) {
      try {
        const canvas = canvasRef.current.canvas.drawing;
        const context = canvas.getContext('2d');
        const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
        const data = imageData.data;
        
        // Get document position and calculate offsets
        const documentElement = document.querySelector('.react-pdf__Page');
        let docOffsetX = 0;
        let docOffsetY = 0;
        
        if (documentElement) {
          const docRect = documentElement.getBoundingClientRect();
          const canvasRect = canvas.getBoundingClientRect();
          
          // Calculate the offset between canvas and document
          docOffsetX = Math.round((canvasRect.left - docRect.left));
          docOffsetY = Math.round((canvasRect.top - docRect.top));
          
          console.log('Canvas/Document offset:', { docOffsetX, docOffsetY });
        }
        
        // Find areas that were drawn on (non-transparent pixels)
        let pixelsDrawn = false;
        const minArea = { x1: canvas.width, y1: canvas.height, x2: 0, y2: 0 };
        let redColor = false;
        let yellowColor = false;
        
        for (let y = 0; y < canvas.height; y++) {
          for (let x = 0; x < canvas.width; x++) {
            const index = (y * canvas.width + x) * 4;
            const alpha = data[index + 3];
            
            if (alpha > 0) {
              pixelsDrawn = true;
              minArea.x1 = Math.min(minArea.x1, x);
              minArea.y1 = Math.min(minArea.y1, y);
              minArea.x2 = Math.max(minArea.x2, x);
              minArea.y2 = Math.max(minArea.y2, y);
              
              // Check the color - looking for red (#FF0000) or yellow (#FFFF00)
              const r = data[index];
              const g = data[index + 1];
              const b = data[index + 2];
              
              // Detect red (high red, low green and blue)
              if (r > 200 && g < 100 && b < 100) {
                redColor = true;
              }
              
              // Detect yellow (high red and green, low blue)
              if (r > 200 && g > 200 && b < 100) {
                yellowColor = true;
              }
            }
          }
        }
        
        // Only create a redaction if pixels were drawn
        if (pixelsDrawn && minArea.x2 >= minArea.x1 && minArea.y2 >= minArea.y1) {
          // Determine redaction type based on color
          // If both colors are detected, prioritize red (permanent)
          const brushRedactionType = redColor ? 'permanent' : (yellowColor ? 'temporary' : redactionType);
          
          // Apply offsets to coordinates to align with document
          // Remove any offset to make coordinates relative to document
          const adjustedX = minArea.x1 - docOffsetX;
          const adjustedY = minArea.y1 - docOffsetY;
          
          const newRedaction = {
            id: `brush-${Date.now()}`,
            text: `Manual ${brushRedactionType.charAt(0).toUpperCase() + brushRedactionType.slice(1)} Redaction`,
            method: 'brush',
            page: pageNumber - 1,
            redaction_type: brushRedactionType, // Use color-based redaction type
            position: {
              x: adjustedX,
              y: adjustedY,
              width: minArea.x2 - minArea.x1 + 1,
              height: minArea.y2 - minArea.y1 + 1
            }
          };
          
          console.log('Created redaction with adjusted coordinates:', newRedaction);
          setSelectedFields([...selectedFields, newRedaction]);
          canvasRef.current.clear();
        }
      } catch (error) {
        console.error("Error in canvas drawing:", error);
      }
    }
  }
  
  // Apply redactions
  async function handleApplyRedactions() {
    if (!uploadedFileState) {
      setError('No file loaded. Please upload a file first.');
      return;
    }
    
    if (redactions.length === 0 && selectedFields.length === 0) {
      setError('No redactions selected. Please select fields or use the brush tool to mark areas for redaction.');
      return;
    }
    
    setLoading(true);
    setError('');
    setSuccess('');
    
    const allRedactions = [
      ...redactions,
      ...selectedFields
    ];
    
    try {
      const response = await apiClient.post('/api/redact', {
        file_id: uploadedFileState.file_id,
        redactions: allRedactions,
        redaction_type: redactionType,
        document_type: uploadedFileState.document_type || 'unknown'
      });
      
      // Show preview and allow download
      setPreviewUrl(getApiUrl(`/api/download/${response.data.redacted_file_id}`));
      setShowPreview(true);
      setSuccess('Document successfully redacted! You can now download the result.');
    } catch (err) {
      console.error('Redaction error:', err);
      if (err.response) {
        setError(err.response.data?.error || `Server error: ${err.response.status}`);
      } else if (err.request) {
        setError('No response from server. Please check your connection.');
      } else {
        setError(`Error: ${err.message}`);
      }
    } finally {
      setLoading(false);
    }
  }
  
  // Download redacted document
  function handleDownload() {
    if (previewUrl) {
      window.location.href = previewUrl;
    }
  }
  
  // Reset all redactions
  function handleReset() {
    setSelectedFields([]);
    setRedactions([]);
    setShowPreview(false);
    setPreviewUrl('');
    setError('');
    setSuccess('');
    
    if (canvasRef.current && activeMode === 'brush') {
      try {
        canvasRef.current.clear();
      } catch (error) {
        console.error("Error clearing canvas:", error);
      }
    }
  }
  
  // Analyze document with AI to detect sensitive fields
  async function analyzeDocumentWithAI() {
    if (!uploadedFileState) {
      setError('No file loaded. Please upload a file first.');
      return;
    }
    
    setIsAnalyzing(true);
    setError('');
    
    try {
      // Make the actual API call to the Gemini AI endpoint
      const response = await apiClient.post('/api/analyze-document', {
        file_id: uploadedFileState.file_id,
        document_type: uploadedFileState.document_type || 'unknown',
        data_fields: uploadedFileState.data_fields || []
      });
      
      // Extract the suggested fields from the response
      const suggestedFields = response.data.sensitive_fields || [];
      
      setAiSuggestedFields(suggestedFields);
      setAiAnalysisComplete(true);
      setSuccess(`AI analysis complete. Found ${suggestedFields.length} potential sensitive fields.`);
      
    } catch (err) {
      console.error('AI analysis error:', err);
      setError('Error during AI analysis. Please try again or proceed with manual selection.');
    } finally {
      setIsAnalyzing(false);
    }
  }
  
  // Add all AI suggested fields to selection
  function applyAllAiSuggestions() {
    setSelectedFields([...selectedFields, ...aiSuggestedFields]);
    setAiSuggestedFields([]);
    setSuccess('All AI suggestions applied successfully.');
  }
  
  // Render document based on file type
  const renderDocument = () => {
    if (!uploadedFileState) {
      return (
        <EmptyState>
          <h3>No document loaded</h3>
          <p>Please upload a document to get started</p>
          <Button primary onClick={() => navigate('/')} style={{ marginTop: '1rem' }}>
            Go to Upload
          </Button>
        </EmptyState>
      );
    }
    
    // If we're showing a preview, render that instead
    if (showPreview && previewUrl) {
      const fileExtension = uploadedFileState.original_filename.split('.').pop().toLowerCase();
      
      if (fileExtension === 'pdf') {
        return (
          <>
            <h3 style={{ marginBottom: '16px', textAlign: 'center' }}>Redacted Document Preview</h3>
            <Document
              file={previewUrl}
              onLoadSuccess={onDocumentLoadSuccess}
              onLoadError={(error) => {
                console.error('PDF preview load error:', error);
                setError(`Error loading redacted PDF preview. Please try downloading directly.`);
                
                // If file not found, add more detail to the error message
                if (error.name === "MissingPDFException") {
                  setError('The redacted PDF could not be found. The temporary file may have expired. Please try redacting again.');
                }
              }}
            >
              <Page 
                pageNumber={pageNumber} 
                width={pageWidth}
                onLoadSuccess={(page) => {
                  setPageHeight(page.height * (pageWidth / page.width));
                }}
                renderTextLayer={false}
                renderAnnotationLayer={false}
              />
            </Document>
            
            {numPages > 1 && (
              <PaginationControls>
                <PageButton
                  onClick={handlePreviousPage}
                  disabled={pageNumber <= 1}
                >
                  Previous
                </PageButton>
                <PageInfo>
                  Page {pageNumber} of {numPages}
                </PageInfo>
                <PageButton
                  onClick={handleNextPage}
                  disabled={pageNumber >= numPages}
                >
                  Next
                </PageButton>
              </PaginationControls>
            )}
          </>
        );
      } else {
        // For images
        return (
          <>
            <h3 style={{ marginBottom: '16px', textAlign: 'center' }}>Redacted Document Preview</h3>
            <img 
              src={previewUrl}
              alt="Redacted Document"
              style={{ maxWidth: '100%', maxHeight: '80vh' }}
            />
          </>
        );
      }
    }

    // Regular document display
    const fileExtension = uploadedFileState.original_filename.split('.').pop().toLowerCase();
    
    if (fileExtension === 'pdf') {
      const pdfUrl = getApiUrl(`/api/download/${uploadedFileState.file_id}`);
      console.log('Loading PDF from URL:', pdfUrl);
      return (
        <>
          <Document
            file={pdfUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={(error) => {
              console.error('PDF load error:', error);
              console.error('Failed to load PDF from:', pdfUrl);
              
              // If file not found, provide a more helpful error message
              if (error.name === "MissingPDFException") {
                setError(`The PDF could not be found on the server. This usually happens because:
                  1. The file was not properly uploaded
                  2. The server storage path is incorrect
                  3. The server may have restarted and cleared temporary files
                
                Please try uploading the document again or contact support if the issue persists.`);
              } else {
                setError(`Error loading PDF: ${error.message}. Please try re-uploading the document.`);
              }
            }}
          >
            <Page 
              pageNumber={pageNumber} 
              width={pageWidth}
              onLoadSuccess={(page) => {
                setPageHeight(page.height * (pageWidth / page.width));
              }}
              renderTextLayer={false}
              renderAnnotationLayer={false}
            />
          </Document>
          
          {numPages > 1 && (
            <PaginationControls>
              <PageButton
                onClick={handlePreviousPage}
                disabled={pageNumber <= 1}
              >
                Previous
              </PageButton>
              <PageInfo>
                Page {pageNumber} of {numPages}
              </PageInfo>
              <PageButton
                onClick={handleNextPage}
                disabled={pageNumber >= numPages}
              >
                Next
              </PageButton>
            </PaginationControls>
          )}
        </>
      );
    } else {
      // For images
      return (
        <img 
          src={getApiUrl(`/api/download/${uploadedFileState.file_id}`)}
          alt="Document"
          style={{ maxWidth: '100%', maxHeight: '80vh' }}
          onLoad={(e) => {
            setPageWidth(e.target.width);
            setPageHeight(e.target.height);
          }}
        />
      );
    }
  };

  // Filter sensitive fields
  const getSensitiveFields = () => {
    if (!uploadedFileState || !uploadedFileState.data_fields) return [];
    
    // If we have AI-suggested fields for the current page, show those first
    const aiFields = aiSuggestedFields.filter(field => field.page === pageNumber - 1);
    
    // Also get manually identified fields
    const manualFields = uploadedFileState.data_fields
      .filter(field => field.page === pageNumber - 1)
      .filter(field => {
        // Check if this field is already in the AI suggestions
        const isInAiSuggestions = aiFields.some(aiField => aiField.id === field.id);
        if (isInAiSuggestions) return false;
        
        // Only show personal/sensitive fields
        const text = field.text.toLowerCase();
        return text.includes('name') || 
               text.includes('address') || 
               text.includes('number') || 
               text.includes('phone') || 
               text.includes('email') || 
               text.includes('dob') || 
               text.includes('birth') || 
               text.includes('aadhar') || 
               text.includes('pan') || 
               text.includes('passport') ||
               text.match(/\b\d{4}\s?\d{4}\s?\d{4}\b/) || // Aadhar pattern
               text.match(/\b[A-Z]{5}\d{4}[A-Z]\b/);      // PAN pattern
      });
    
    // Combine both sets, putting AI suggestions first
    return [...aiFields, ...manualFields];
  };

  return (
    <EditorContainer>
      <DocumentPane ref={documentRef}>
        {/* Always render the document, regardless of mode */}
        {renderDocument()}
        
        {/* Only render canvas when document is loaded and brush mode is active */}
        {uploadedFileState && pageWidth > 0 && pageHeight > 0 && activeMode === 'brush' && !showPreview && (
          <CanvasWrapper active={activeMode === 'brush'}>
            <div style={{ 
              position: 'relative', 
              width: pageWidth, 
              height: pageHeight,
              overflow: 'hidden'
            }}>
              <CanvasDraw
                ref={canvasRef}
                brushColor={getBrushColor()}
                brushRadius={brushSize}
                lazyRadius={0}
                canvasWidth={pageWidth}
                canvasHeight={pageHeight}
                onChange={handleCanvasDraw}
                hideGrid={true}
                immediateLoading={true}
                backgroundColor="rgba(0, 0, 0, 0)"
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  opacity: 0.8
                }}
              />
            </div>
          </CanvasWrapper>
        )}
      </DocumentPane>
      
      <ControlPane>
        <SectionTitle>RedactAI Document Editor</SectionTitle>
        
        {!showPreview ? (
          <>
            <Section>
              <SectionTitle>Redaction Mode</SectionTitle>
              <ModeTabs>
                <ModeTab
                  active={activeMode === 'select'}
                  onClick={() => handleModeChange('select')}
                >
                  Field Selection
                </ModeTab>
                <ModeTab
                  active={activeMode === 'brush'}
                  onClick={() => handleModeChange('brush')}
                >
                  Manual Drawing
                </ModeTab>
              </ModeTabs>
              
              <div style={{ marginTop: '10px', fontSize: '13px', color: '#555', fontStyle: 'italic' }}>
                {activeMode === 'brush' ? 
                  'Draw directly on the document. Red = permanent redaction, Yellow = temporary redaction.' : 
                  'Select fields from the list on the right to mark them for redaction.'}
              </div>
            </Section>
            
            <Section>
              <SectionTitle>Redaction Type</SectionTitle>
              <RedactionOptions>
                <RedactionOption 
                  selected={redactionType === 'temporary'}
                  onClick={() => handleRedactionTypeChange('temporary')}
                >
                  <ColorIndicator color="#FFFF00" />
                  <OptionLabel>Temporary</OptionLabel>
                </RedactionOption>
                <RedactionOption
                  selected={redactionType === 'permanent'}
                  onClick={() => handleRedactionTypeChange('permanent')}
                >
                  <ColorIndicator color="#FF0000" />
                  <OptionLabel>Permanent</OptionLabel>
                </RedactionOption>
              </RedactionOptions>
            </Section>
            
            {/* AI Analysis Section */}
            <Section>
              <SectionTitle>AI Document Analysis</SectionTitle>
              <p>Having trouble identifying sensitive data? Our AI can help analyze your document.</p>
              <Button 
                primary
                onClick={analyzeDocumentWithAI} 
                disabled={isAnalyzing}
                style={{ marginTop: '12px' }}
              >
                {isAnalyzing ? <><LoadingSpinner />Analyzing...</> : 'Analyze with AI'}
              </Button>
              
              {aiAnalysisComplete && aiSuggestedFields.length > 0 && (
                <div style={{ marginTop: '16px' }}>
                  <InfoMessage>
                    AI found {aiSuggestedFields.length} potentially sensitive fields in your document.
                  </InfoMessage>
                  <Button 
                    onClick={applyAllAiSuggestions} 
                    style={{ marginTop: '8px' }}
                  >
                    Apply All AI Suggestions
                  </Button>
                </div>
              )}
            </Section>
            
            {activeMode === 'select' && (
              <Section>
                <SectionTitle>
                  Sensitive Fields
                  {getSensitiveFields().length > 0 ? ` (${getSensitiveFields().length})` : ''}
                </SectionTitle>
                
                <FieldList>
                  {getSensitiveFields().length > 0 ? (
                    getSensitiveFields().map(field => (
                      <FieldItem
                        key={field.id}
                        selected={selectedFields.some(f => f.id === field.id)}
                        onClick={() => handleFieldSelect(field)}
                      >
                        <FieldName>
                          {field.text}
                          {field.category && (
                            <span style={{ 
                              fontSize: '12px', 
                              backgroundColor: '#e3f2fd', 
                              color: '#0d47a1',
                              borderRadius: '4px',
                              padding: '2px 6px',
                              marginLeft: '8px'
                            }}>
                              {field.category}
                            </span>
                          )}
                        </FieldName>
                        <FieldValue>
                          Confidence: {field.ai_confidence || field.confidence}%
                          {field.ai_confidence && (
                            <span style={{ 
                              color: '#4caf50', 
                              fontWeight: 'bold', 
                              marginLeft: '8px' 
                            }}>
                              AI Suggested
                            </span>
                          )}
                          {field.reason && (
                            <div style={{ 
                              fontSize: '12px', 
                              fontStyle: 'italic',
                              color: '#555',
                              marginTop: '4px'
                            }}>
                              Reason: {field.reason}
                            </div>
                          )}
                        </FieldValue>
                        
                        {/* Redaction controls - only visible when field is selected */}
                        <FieldControls visible={selectedFields.some(f => f.id === field.id)}>
                          <div style={{ fontSize: '12px', marginRight: '8px' }}>Redaction:</div>
                          <RedactionTypeButton 
                            permanent={false}
                            selected={selectedFields.some(f => f.id === field.id && f.redaction_type === 'temporary')}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleFieldRedactionTypeChange(field.id, 'temporary');
                            }}
                          >
                            Temporary
                          </RedactionTypeButton>
                          <RedactionTypeButton 
                            permanent={true}
                            selected={selectedFields.some(f => f.id === field.id && f.redaction_type === 'permanent')}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleFieldRedactionTypeChange(field.id, 'permanent');
                            }}
                          >
                            Permanent
                          </RedactionTypeButton>
                        </FieldControls>
                      </FieldItem>
                    ))
                  ) : (
                    <EmptyState style={{ padding: '20px' }}>
                      {aiAnalysisComplete ? 
                        <p>No sensitive fields detected on this page, even with AI analysis. Try using the manual drawing tool.</p> :
                        <p>No sensitive fields detected on this page. Try using AI analysis or the manual drawing tool.</p>
                      }
                    </EmptyState>
                  )}
                </FieldList>
              </Section>
            )}
            
            {activeMode === 'brush' && (
              <Section>
                <SectionTitle>Manual Redaction</SectionTitle>
                <p style={{ marginBottom: '10px' }}>
                  Draw directly on the document to redact specific areas.
                </p>
                <p>
                  Current color: <ColorIndicator color={getBrushColor()} /> 
                  {redactionType === 'temporary' ? ' Temporary' : ' Permanent'} redaction
                </p>
                
                {/* Brush Size Control */}
                <div style={{ marginTop: '15px' }}>
                  <p style={{ marginBottom: '5px', fontSize: '14px' }}>Brush Size: {brushSize}</p>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <span style={{ fontSize: '12px', marginRight: '8px' }}>Small</span>
                    <input 
                      type="range" 
                      min="3" 
                      max="20" 
                      value={brushSize} 
                      onChange={(e) => setBrushSize(parseInt(e.target.value))}
                      style={{ flex: 1 }}
                    />
                    <span style={{ fontSize: '12px', marginLeft: '8px' }}>Large</span>
                  </div>
                </div>
              </Section>
            )}
            
            <Section>
              <SectionTitle>Redaction Summary</SectionTitle>
              <SummaryItem>
                <span>Selected fields:</span>
                <span>{selectedFields.length}</span>
              </SummaryItem>
              <SummaryItem>
                <span>Manual redactions:</span>
                <span>{redactions.length}</span>
              </SummaryItem>
              <SummaryItem>
                <span>Redaction type:</span>
                <span style={{ display: 'flex', alignItems: 'center' }}>
                  <ColorIndicator color={getBrushColor()} style={{ marginRight: '5px' }} />
                  {redactionType === 'temporary' ? 'Temporary' : 'Permanent'}
                </span>
              </SummaryItem>
            </Section>
            
            {error && <ErrorMessage>{error}</ErrorMessage>}
            {success && <SuccessMessage>{success}</SuccessMessage>}
            
            <ButtonGroup>
              <Button 
                primary
                onClick={handleApplyRedactions}
                disabled={loading || (selectedFields.length === 0 && redactions.length === 0)}
              >
                {loading ? <><LoadingSpinner />Processing...</> : 'Apply Redactions'}
              </Button>
              
              <Button 
                danger
                onClick={handleReset}
                disabled={loading || (selectedFields.length === 0 && redactions.length === 0)}
              >
                Reset All
              </Button>
            </ButtonGroup>
          </>
        ) : (
          <>
            <Section>
              <SectionTitle>Redaction Complete</SectionTitle>
              <p style={{ marginBottom: '20px' }}>
                Your document has been successfully redacted with the following settings:
              </p>
              <SummaryItem>
                <span>Fields redacted:</span>
                <span>{selectedFields.length}</span>
              </SummaryItem>
              <SummaryItem>
                <span>Manual areas:</span>
                <span>{redactions.length}</span>
              </SummaryItem>
              <SummaryItem>
                <span>Redaction type:</span>
                <span style={{ display: 'flex', alignItems: 'center' }}>
                  <ColorIndicator color={getBrushColor()} style={{ marginRight: '5px' }} />
                  {redactionType === 'temporary' ? 'Temporary' : 'Permanent'}
                </span>
              </SummaryItem>
            </Section>
            
            <ButtonGroup>
              <Button 
                primary
                onClick={handleDownload}
              >
                Download Redacted Document
              </Button>
              
              <Button 
                onClick={handleReset}
              >
                Edit Redactions
              </Button>
              
              <Button 
                onClick={() => navigate('/')}
              >
                Upload New Document
              </Button>
            </ButtonGroup>
          </>
        )}
      </ControlPane>
    </EditorContainer>
  );
}

export default EditorPage;
