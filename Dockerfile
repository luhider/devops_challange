FROM python:3.11

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential curl git vim net-tools

COPY . /app
RUN chmod 0755 /app /app/models

EXPOSE 8000 9000

CMD ["python", "vision_api/app.py"]
