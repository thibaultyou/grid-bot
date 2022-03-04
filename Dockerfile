FROM python:3.8

WORKDIR /code

ADD requirements.txt .

RUN python3 -m pip install -r requirements.txt

ADD src ./src

ADD main.py .

ADD .env .

RUN mkdir logs

CMD [ "python3", "-u", "main.py" ]