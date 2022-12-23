FROM python:3.9-slim

COPY requirements.txt ./

RUN pip3 install -r requirements.txt
COPY compare.py ./

ARG MASTODON_BASE
ARG MASTODON_TOKEN
ARG TUMBLR_URL
ENV TZ=America/Los_Angeles \
    MASTODON_BASE=$MASTODON_BASE \
    MASTODON_TOKEN=$MASTODON_TOKEN \
    TUMBLR_URL=$TUMBLR_URL

CMD python3 compare.py
