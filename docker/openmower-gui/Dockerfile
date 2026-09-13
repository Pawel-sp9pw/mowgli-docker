FROM alpine/git:latest AS source
ARG GUI_REPO=https://github.com/cedbossneo/openmower-gui.git
# Match the backend source to the ghcr.io/cedbossneo/openmower-gui:v2 runtime/frontend.
ARG GUI_REF=41ec7b529fb55720006922aee35d4b54795052d9
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

# Keep the packaged v2 frontend/runtime and replace only the matching patched
# v2 backend. This avoids ARM64 yarn/network failures and keeps API versions
# aligned (power/emergency/dockingSensor/system info included).
FROM ghcr.io/cedbossneo/openmower-gui:v2
COPY --from=build-go /app/openmower-gui /app/openmower-gui
WORKDIR /app
