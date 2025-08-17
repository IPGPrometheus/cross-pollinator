FROM python:3.11-alpine

RUN apk add --no-cache bash sqlite

WORKDIR /app

COPY cross-pollinator.py /app/
RUN chmod +x /app/cross-pollinator.py

RUN echo '#!/bin/bash' > /usr/local/bin/cross-pollinator && \
    echo 'python3 /app/cross-pollinator.py "$@"' >> /usr/local/bin/cross-pollinator && \
    chmod +x /usr/local/bin/cross-pollinator

RUN echo '#!/bin/bash' > /app/entrypoint.sh && \
    echo 'echo "Cross-Pollinator ready!"' >> /app/entrypoint.sh && \
    echo 'echo "Usage: cross-pollinator --run [--stats]"' >> /app/entrypoint.sh && \
    echo 'tail -f /dev/null' >> /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
