# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
	useradd -m appuser
USER appuser

# Copy the rest of the application code into the container
COPY . .

# Expose port 80 for the Flask app
EXPOSE 80

# Run the application
CMD ["python", "main.py"]
