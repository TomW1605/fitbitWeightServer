FROM python:3.10
LABEL authors="Thomas White"

WORKDIR /usr/src

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

ENTRYPOINT ["python", "-m", "flask", "run", "--host=0.0.0.0"]