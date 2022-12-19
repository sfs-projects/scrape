FROM python:3.10

COPY requirements.txt .
COPY main.py .


RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
