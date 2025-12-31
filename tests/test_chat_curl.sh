#!/bin/bash
echo "Testing Chat API via Curl..."
curl -X POST http://localhost:8088/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What trends are in namespace 44e3e292-a021-4026-aa4e-78eb7b165647?", 
    "history": [], 
    "model": "llama3.1"
  }'
echo -e "\nDone."
