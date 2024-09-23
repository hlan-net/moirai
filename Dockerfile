# Use the official Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file and the application code
COPY requirements.txt .
COPY app.py .
COPY templates/ ./templates

# Install the necessary packages
RUN pip install --no-cache-dir -r requirements.txt

# Specify the command to run the application
CMD ["python", "app.py"]
