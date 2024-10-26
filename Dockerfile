FROM python:3.12-slim

COPY ./app /app
COPY ./requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --upgrade -r ./requirements.txt

CMD ["fastapi", "run", /"app/main.py", "--port", "80"]
