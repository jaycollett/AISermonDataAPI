# Use official Python image as base
FROM python:3.10

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py \
    FLASK_RUN_HOST=0.0.0.0 \
    FLASK_RUN_PORT=5090 \
    OPENAI_API_KEY="your-openai-api-key"

# Set the working directory
WORKDIR /app

# Copy the application files
COPY . .

# Install dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Expose the API port
EXPOSE 5090

# Start both the API and the worker process
CMD ["sh", "-c", "python app.py"]
