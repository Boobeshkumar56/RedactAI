#!/bin/bash

echo "Fixing RedactAI Canvas Drawing Error"
echo "------------------------------------"

cd /home/boobesh/projects/RedactAi/ocr/frontend

# Remove node_modules and package-lock.json
echo "Cleaning up existing installation..."
rm -rf node_modules package-lock.json

# Install a more compatible version of react-canvas-draw
echo "Installing a compatible version of react-canvas-draw..."
npm install --save react-canvas-draw@1.1.1

# Install all other dependencies
echo "Installing remaining dependencies..."
npm install

echo "Installation complete! Please start the application again with:"
echo "cd /home/boobesh/projects/RedactAi/ocr/frontend"
echo "npm start"
