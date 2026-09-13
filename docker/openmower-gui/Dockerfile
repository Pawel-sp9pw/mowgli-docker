FROM alpine/git:latest AS source
ARG GUI_REPO=https://github.com/cedbossneo/openmower-gui.git
ARG GUI_REF=2de67f9914b1fff38a75f495e47aed8c18917f70
RUN git clone "$GUI_REPO" /src \
    && cd /src \
    && git checkout "$GUI_REF"
COPY docker/openmower-gui/compat.patch /tmp/compat.patch
RUN cd /src \
    && git apply --check /tmp/compat.patch \
    && git apply /tmp/compat.patch

FROM golang:1.21 AS build-go
COPY --from=source /src /app
WORKDIR /app
RUN CGO_ENABLED=0 go build -o openmower-gui

FROM node:18 AS build-web
COPY --from=source /src/web /web
WORKDIR /web
RUN yarn && yarn build

FROM ubuntu:22.04 AS deps
RUN apt-get update && apt-get install -y ca-certificates curl python3 python3-pip python3-venv libjim-dev \
    git build-essential unzip wget autoconf automake pkg-config texinfo libtool libftdi-dev libusb-1.0-0-dev \
    && apt-get install -y rpi.gpio-common || true
RUN git clone --recursive --branch rpi-common --depth=1 https://github.com/raspberrypi/openocd.git \
    && cd openocd \
    && ./bootstrap with-submodules \
    && ./configure --enable-ftdi --enable-sysfsgpio --enable-bcm2835gpio \
    && make -j"$(nproc)" \
    && make install \
    && cd .. \
    && rm -rf openocd
RUN curl -fsSL https://raw.githubusercontent.com/platformio/platformio-core-installer/master/get-platformio.py -o get-platformio.py \
    && python3 get-platformio.py
RUN python3 -m pip install --upgrade pygnssutils
RUN mkdir -p /usr/local/bin \
    && ln -s ~/.platformio/penv/bin/platformio /usr/local/bin/platformio \
    && ln -s ~/.platformio/penv/bin/pio /usr/local/bin/pio \
    && ln -s ~/.platformio/penv/bin/piodebuggdb /usr/local/bin/piodebuggdb

FROM deps
COPY --from=source /src/setup /app/setup
COPY --from=build-web /web/dist /app/web
COPY --from=build-go /app/openmower-gui /app/openmower-gui
ENV WEB_DIR=/app/web
ENV DB_PATH=/app/db
WORKDIR /app
CMD ["/app/openmower-gui"]
