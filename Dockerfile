# libgourou is fetched at a pinned commit and patched before it is compiled.
# python:3.12-slim (unpinned) is Debian 13 as of October 2026, whose libzip/libssl
# sonames differ from bookworm. Both stages stay on bookworm so the sketch's
# runtime packages (libzip4, libssl3, libcurl4) match the libraries used to link.

FROM debian:bookworm-slim AS gourou
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential git ca-certificates patch \
      libpugixml-dev libcurl4-openssl-dev libssl-dev libzip-dev zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*
ARG LIBGOUROU_REPO=https://github.com/rledisez/libgourou.git
ARG LIBGOUROU_COMMIT=906b8a37334ac5d37dcae24c7508a427c19dbb66
WORKDIR /src
RUN git clone "$LIBGOUROU_REPO" libgourou \
 && git -C libgourou checkout "$LIBGOUROU_COMMIT"
COPY patches/libgourou-no-drm-removal.patch /src/libgourou-no-drm-removal.patch
COPY third_party/updfparser /src/updfparser
# Run make from the source directory. The upstream Makefile passes ROOT=$(PWD)
# into utils/, and an inherited PWD from `make -C` points at the wrong tree.
RUN cd /src/libgourou \
 && patch -p1 < /src/libgourou-no-drm-removal.patch \
 && rm -f /src/libgourou-no-drm-removal.patch \
 && mkdir -p lib \
 && cp -a /src/updfparser lib/updfparser \
 && make -C lib/updfparser BUILD_STATIC=1 BUILD_SHARED=0 \
 && make BUILD_UTILS=1 \
 && test ! -e utils/adept_remove \
 && test ! -e utils/adept_remove.cpp \
 && mkdir -p /opt/licenses/libgourou /opt/licenses/updfparser \
 && cp -a include src utils LICENSE README.md Makefile /opt/licenses/libgourou/ \
 && rm -rf /opt/licenses/libgourou/utils/*.o /opt/licenses/libgourou/utils/*.a \
           /opt/licenses/libgourou/utils/acsmdownloader \
           /opt/licenses/libgourou/utils/adept_activate \
           /opt/licenses/libgourou/utils/adept_loan_mgt \
           /opt/licenses/libgourou/utils/launcher \
 && cp -a /src/updfparser/include /src/updfparser/src /src/updfparser/LICENSE \
          /src/updfparser/README.md /src/updfparser/Makefile /opt/licenses/updfparser/

FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web /web
COPY shared /shared
RUN npm run build

FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpugixml1v5 libcurl4 libssl3 libzip4 zlib1g \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --uid 1000 --no-create-home --home-dir /tmp --shell /usr/sbin/nologin liseo
COPY --from=gourou /src/libgourou/libgourou.so /src/libgourou/libgourou.so.0.8.10 /usr/local/lib/
COPY --from=gourou /src/libgourou/utils/adept_activate \
                   /src/libgourou/utils/acsmdownloader \
                   /src/libgourou/utils/adept_loan_mgt /usr/local/bin/
COPY --from=gourou /opt/licenses /usr/local/src/liseo-third-party
COPY --from=web /web/dist /app/static
COPY backend/requirements.txt /app/requirements.txt
COPY backend/liseo /app/liseo
COPY docker/entrypoint.py /usr/local/bin/liseo-entrypoint
RUN ldconfig \
 && pip install --no-cache-dir -r /app/requirements.txt \
 && chmod 755 /usr/local/bin/liseo-entrypoint /usr/local/bin/adept_activate \
              /usr/local/bin/acsmdownloader /usr/local/bin/adept_loan_mgt \
 && test ! -e /usr/local/bin/adept_remove
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HOME=/tmp \
    TMPDIR=/tmp
WORKDIR /app
VOLUME /data
EXPOSE 8080
ENTRYPOINT ["python3", "/usr/local/bin/liseo-entrypoint"]
CMD ["uvicorn", "liseo.main:app", "--host", "0.0.0.0", "--port", "8080"]
