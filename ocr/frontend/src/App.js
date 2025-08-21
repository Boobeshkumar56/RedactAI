import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import styled from 'styled-components';
import Header from './components/Header';
import UploadPage from './components/UploadPage';
import EditorPage from './components/EditorPage';
import './App.css';

const AppContainer = styled.div`
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: #f8f9fa;
`;

function App() {
  const [uploadedFile, setUploadedFile] = useState(null);
  
  return (
    <Router>
      <AppContainer>
        <Header />
        <Routes>
          <Route 
            path="/" 
            element={<UploadPage setUploadedFile={setUploadedFile} />} 
          />
          <Route 
            path="/editor" 
            element={<EditorPage uploadedFile={uploadedFile} />} 
          />
        </Routes>
      </AppContainer>
    </Router>
  );
}

export default App;
