FROM alpine:3.20

RUN apk add --no-cache curl jq

COPY backup-loop.sh /backup-loop.sh
RUN chmod +x /backup-loop.sh

ENTRYPOINT ["/backup-loop.sh"]
