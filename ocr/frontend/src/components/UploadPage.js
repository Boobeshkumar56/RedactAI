import React, { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';
import styled from 'styled-components';

const UploadContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 2rem;
`;

const UploadCard = styled.div`
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  width: 100%;
  max-width: 600px;
  padding: 2rem;
  text-align: center;
`;

const DropzoneArea = styled.div`
  border: 2px dashed ${props => props.isDragActive ? '#3f51b5' : '#ccc'};
  border-radius: 4px;
  padding: 3rem 2rem;
  margin: 1.5rem 0;
  transition: border-color 0.3s ease;
  cursor: pointer;
  background-color: ${props => props.isDragActive ? '#f0f4ff' : '#f9f9f9'};

  &:hover {
    border-color: #3f51b5;
  }
`;

const Title = styled.h2`
  margin-bottom: 0.5rem;
  color: #333;
`;

const Subtitle = styled.p`
  color: #666;
  margin-bottom: 1.5rem;
`;

const FileInfo = styled.div`
  margin-top: 1.5rem;
  padding: 1rem;
  background-color: #f5f5f5;
  border-radius: 4px;
  text-align: left;
`;

const UploadButton = styled.button`
  background-color: #3f51b5;
  color: white;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 4px;
  font-weight: 500;
  font-size: 1rem;
  cursor: pointer;
  transition: background-color 0.3s ease;
  margin-top: 1.5rem;

  &:hover {
    background-color: #303f9f;
  }

  &:disabled {
    background-color: #b0bec5;
    cursor: not-allowed;
  }
`;

const LoadingSpinner = styled.div`
  border: 4px solid rgba(0, 0, 0, 0.1);
  border-radius: 50%;
  border-top: 4px solid #3f51b5;
  width: 30px;
  height: 30px;
  margin: 0 auto;
  animation: spin 1s linear infinite;

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
`;

const ErrorMessage = styled.p`
  color: #f44336;
  margin-top: 0.5rem;
`;

const DocumentTypeSelector = styled.div`
  margin-top: 1.5rem;
  text-align: left;
`;

const SelectWrapper = styled.div`
  margin-top: 0.5rem;
`;

const StyledSelect = styled.select`
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: white;
  font-size: 1rem;
  appearance: none;
  background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
  background-repeat: no-repeat;
  background-position: right 1rem center;
  background-size: 1em;
`;

function UploadPage({ setUploadedFile }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [documentType, setDocumentType] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const onDrop = useCallback(acceptedFiles => {
    if (acceptedFiles.length > 0) {
      setSelectedFile(acceptedFiles[0]);
      setError('');
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ 
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']
    },
    maxFiles: 1,
    onDropRejected: () => {
      setError('Please upload a valid PDF or image file.');
    }
  });

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Please select a file to upload.');
      return;
    }

    if (!documentType) {
      setError('Please select a document type.');
      return;
    }

    setLoading(true);
    setError('');

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('documentType', documentType);

    try {
      const response = await axios.post('/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      // Save to local storage in case of page refresh
      const fileData = {
        ...response.data,
        originalFile: {
          name: selectedFile.name,
          size: selectedFile.size,
          type: selectedFile.type
        },
        documentType
      };
      
      localStorage.setItem('uploadedFile', JSON.stringify(fileData));
      
      setUploadedFile(fileData);
      
      navigate('/editor');
    } catch (err) {
      console.error('Upload error:', err);
      setError(err.response?.data?.error || 'Failed to upload file. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <UploadContainer>
      <UploadCard>
        <Title>Upload Document</Title>
        <Subtitle>Drag & drop your PDF or image file to redact sensitive information</Subtitle>

        <DropzoneArea {...getRootProps()} isDragActive={isDragActive}>
          <input {...getInputProps()} />
          {isDragActive ? (
            <p>Drop the file here...</p>
          ) : (
            <div>
              <p>Drag and drop a file here, or click to select a file</p>
              <small>Supported formats: PDF, JPG, PNG, BMP, TIFF</small>
            </div>
          )}
        </DropzoneArea>

        {selectedFile && (
          <FileInfo>
            <p><strong>Selected file:</strong> {selectedFile.name}</p>
            <p><strong>Size:</strong> {(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
            <p><strong>Type:</strong> {selectedFile.type}</p>
          </FileInfo>
        )}

        {selectedFile && (
          <DocumentTypeSelector>
            <h3>Document Type</h3>
            <p>Select the type of document you're uploading</p>
            <SelectWrapper>
              <StyledSelect 
                value={documentType} 
                onChange={(e) => setDocumentType(e.target.value)}
              >
                <option value="">-- Select Document Type --</option>
                <option value="aadhar">Aadhar Card</option>
                <option value="pan">PAN Card</option>
                <option value="passport">Passport</option>
                <option value="driving_license">Driving License</option>
                <option value="voter_id">Voter ID</option>
                <option value="bank_statement">Bank Statement</option>
                <option value="medical_record">Medical Record</option>
                <option value="other">Other</option>
              </StyledSelect>
            </SelectWrapper>
          </DocumentTypeSelector>
        )}

        {error && <ErrorMessage>{error}</ErrorMessage>}

        <UploadButton 
          onClick={handleUpload} 
          disabled={!selectedFile || loading}
        >
          {loading ? <LoadingSpinner /> : 'Upload & Process'}
        </UploadButton>
      </UploadCard>
    </UploadContainer>
  );
}

export default UploadPage;
