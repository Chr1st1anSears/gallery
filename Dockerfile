# Use an official lightweight Python image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED True
ENV APP_HOME /app

# Set the working directory in the container
WORKDIR $APP_HOME

# Copy the requirements file and install dependencies
# This is done in a separate step to take advantage of Docker's layer caching.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the rest of the application's source code
COPY . .

# Command to run the Gunicorn server
# It listens on port 8080, which Cloud Run expects by default.
CMD ["gunicorn", "-b", "0.0.0.0:8080", "main:app"]
