# We will use python:3.10-alpine as the base image for building the Flask container
FROM ubuntu:latest
# It specifies the working directory where the Docker container will run
WORKDIR /app
# Copying all the application files to the working directory
COPY . .


RUN apt-get update -qq && apt-get install ffmpeg -y

RUN apt-get install -y python3-pip

# Install all the dependencies required to run the Flask application
RUN pip install -r requirements.txt

ENV GOOGLE_APPLICATION_CREDENTIALS=key.json
# Expose the Docker container for the application to run on port 5000
EXPOSE 3000
# The command required to run the Dockerized application
CMD ["python3", "/app/app.py"]