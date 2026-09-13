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

# The compatibility fix is backend-only. Keep the frontend and runtime from
# the known-good v2 image, avoiding an unnecessary ARM64 yarn install/build.
FROM ghcr.io/cedbossneo/openmower-gui:v2
COPY --from=build-go /app/openmower-gui /app/openmower-gui
WORKDIR /app
