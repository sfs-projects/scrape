FROM python:3.10

ADD requirements.txt .
ADD main.py .


RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
