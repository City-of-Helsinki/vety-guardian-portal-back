FROM registry.access.redhat.com/ubi10/python-314-minimal

# Branch or tag used to pull python-uwsgi-common.
ARG UWSGI_COMMON_REF=main

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# uv configuration
ENV UV_PROJECT_ENVIRONMENT=/opt/app-root \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never
ENV PATH="${UV_PROJECT_ENVIRONMENT}/bin:${PATH}"

COPY --from=ghcr.io/astral-sh/uv:0.12.22@sha256:f513a91fc62fe7c17567eee97230dd198e43edb8a9fbecca843714a4358fe1bc /uv /uvx /usr/local/bin/

WORKDIR /app

USER root

COPY pyproject.toml uv.lock ./

# gcc, python3.14-devel and pcre2-devel are needed to compile uWSGI and its plugins, tar and gzip to unpack python-uwsgi-common.
RUN microdnf update -y && \
    microdnf install -y nmap-ncat gcc python3.14-devel pcre2-devel tar gzip && \
    microdnf clean all && \
    uv sync --locked --no-install-project --no-dev --group prod

# Build and copy specific python-uwsgi-common files.
ADD https://github.com/City-of-Helsinki/python-uwsgi-common/archive/${UWSGI_COMMON_REF}.tar.gz /usr/src/
RUN mkdir -p /usr/src/python-uwsgi-common && \
    tar --strip-components=1 -xzf /usr/src/${UWSGI_COMMON_REF}.tar.gz -C /usr/src/python-uwsgi-common && \
    cp /usr/src/python-uwsgi-common/uwsgi-base.ini /app/ && \
    uwsgi --build-plugin /usr/src/python-uwsgi-common && \
    rm -rf /usr/src/${UWSGI_COMMON_REF}.tar.gz && \
    rm -rf /usr/src/python-uwsgi-common

COPY . .

# Static files are collected at container start (docker-entrypoint.sh), so the directory must be writable.
# Group 0 permissions allow OpenShift's arbitrary user IDs to write to it.
ENV STATIC_ROOT=/var/static
RUN mkdir -p ${STATIC_ROOT} && \
    chown 1001:0 ${STATIC_ROOT} && \
    chmod g+rwX ${STATIC_ROOT}

USER 1001
EXPOSE 8000/tcp

ENTRYPOINT ["/app/docker-entrypoint.sh"]
