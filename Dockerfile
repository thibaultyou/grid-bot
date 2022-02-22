FROM python

WORKDIR /code

ADD requirements.txt .

RUN python3 -m pip install -r requirements.txt

ADD src ./src

ADD main.py .

ADD .env .

CMD [ "python3", "main.py" ]