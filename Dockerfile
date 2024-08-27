# Use the official Python image from the Docker Hub
FROM python:3.8-slim

# Set the working directory in the container
WORKDIR /app

# Copy the application code and data files into the container
COPY app /app

# Install the required Python packages
COPY requirements.txt /app/
RUN pip install -r requirements.txt

# Expose port 5679 for the application
EXPOSE 5679

# Define the command to run the application
CMD ["python", "server_multi_tcp.py"]
