FROM alpine/git:latest AS source
ARG GUI_REPO=https://github.com/cedbossneo/openmower-gui.git
ARG GUI_REF=2de67f9914b1fff38a75f495e47aed8c18917f70
RUN apk add --no-cache python3
RUN git clone "$GUI_REPO" /src \
    && cd /src \
    && git checkout "$GUI_REF"
COPY docker/openmower-gui/apply_compat.py /tmp/apply_compat.py
RUN python3 /tmp/apply_compat.py

FROM golang:1.21 AS build-go
COPY --from=source /src /app
WORKDIR /app
RUN CGO_ENABLED=0 go build -o openmower-gui

FROM node:18 AS build-web
COPY --from=source /src/web /web
WORKDIR /web
RUN yarn --frozen-lockfile && yarn build

# Reuse the known-good legacy GUI runtime image instead of rebuilding OpenOCD,
# PlatformIO and Python tooling for every architecture.  The compatibility
# change only affects the GUI binary/web assets, so keep the proven runtime
# and replace just those artifacts.
FROM ghcr.io/cedbossneo/openmower-gui:v2
COPY --from=source /src/setup /app/setup
COPY --from=build-web /web/dist /app/web
COPY --from=build-go /app/openmower-gui /app/openmower-gui
ENV WEB_DIR=/app/web
ENV DB_PATH=/app/db
WORKDIR /app
CMD ["/app/openmower-gui"]
