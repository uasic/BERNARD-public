# syntax=docker/dockerfile:1

# Comments are provided throughout this file to help you get started.
# If you need more help, visit the Dockerfile reference guide at
# https://docs.docker.com/go/dockerfile-reference/

# Want to help us make this template better? Share your feedback here: https://forms.gle/ybq9Krt8jtBL3iCk7

# Start with Ubuntu 22.04 as the base image
#FROM ubuntu:22.04

# Start with Ubuntu 24.04 as the base image
FROM ubuntu:24.04

# Set environment variables to avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Update and install dependencies
RUN apt-get update && apt-get install -y \
    # General utilities and system tools
    software-properties-common \
    dirmngr \
    curl \
    gnupg \
    lsb-release \
    wget \
    git \
    build-essential \
    cmake \
    pkg-config \
    zlib1g-dev \
    libssl-dev \
    libffi-dev \
    libreadline-dev \
    libbz2-dev \
    libsqlite3-dev \
    liblzma-dev \
    libncursesw5-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libcurl4-openssl-dev \
    libgit2-dev \
    # Graphics and imaging
    libfreetype6-dev \
    libpng-dev \
    libtiff5-dev \
    libjpeg-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libfontconfig1-dev \
    libcairo2-dev \
    libavfilter-dev \
    libmagick++-dev \
    librsvg2-dev \
    # GUI / rendering (X11 / OpenGL)
    libx11-dev \
    libglu1-mesa-dev \
    freeglut3-dev \
    mesa-common-dev \
    # Scientific and geospatial
    libnetcdf-dev \
    netcdf-bin \
    libpoppler-cpp-dev \
    libmysqlclient-dev \
    libpq-dev \
    libsodium-dev \
    libtirpc-dev \
    libgdal-dev \
    gdal-bin \
    libudunits2-dev \
    libblas-dev \
    liblapack-dev \
    gfortran

# ---------------------
# Install Python 3.12.2
# ---------------------
RUN add-apt-repository ppa:deadsnakes/ppa && apt-get update && \
    apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip && \
    ln -s /usr/bin/python3.12 /usr/bin/python

# Ensure pip is updated
RUN apt-get update && apt-get install -y python3-pip

# ---------------------
# Install R 4.4.1
# ---------------------
#RUN curl -fsSL https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/cran.gpg && \
#    add-apt-repository "deb https://cloud.r-project.org/bin/linux/ubuntu $(lsb_release -cs)-cran40/" && \
#    apt-get update && \
#    apt-get install -y --no-install-recommends r-base r-cran-tidyverse

# Add CRAN GPG key
RUN wget -qO- https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc | tee /etc/apt/trusted.gpg.d/cran_ubuntu_key.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/cran.gpg && \
    add-apt-repository "deb https://cloud.r-project.org/bin/linux/ubuntu $(lsb_release -cs)-cran40/" && \
    apt-get update && \
    apt-get install -y --no-install-recommends r-base r-cran-tidyverse

# Add CRAN repository manually (for Ubuntu 24.04 aka noble)
RUN echo "deb https://cloud.r-project.org/bin/linux/ubuntu noble-cran40/" > /etc/apt/sources.list.d/cran-r.list

RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y r-base r-base-dev r-recommended r-cran-tidyverse

WORKDIR /app

# ---------------------
# Install R packages during the build
# ---------------------

RUN Rscript -e "if (!requireNamespace('BiocManager', quietly = TRUE)) install.packages('BiocManager')" && \
    Rscript -e "BiocManager::install(c('BiocParallel', 'MBECS', 'preprocessCore', 'phyloseq', 'ruv', 'sva', 'limma', 'Biobase', 'TreeSummarizedExperiment', 'PLSDAbatch', 'mixOmics'))"
COPY RPackages.R /app/
RUN Rscript RPackages.R

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

# Create a non-privileged user that the app will run under.
# See https://docs.docker.com/go/dockerfile-user-best-practices/
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser

# ---------------------
# Install R packages with cache
# ---------------------

# Set the R library path (optional, for user-level installation)
RUN mkdir -p /home/appuser/R/library && chown -R appuser:appuser /home/appuser/R/library
ENV R_LIBS_USER=/home/appuser/R/library

# Install R packages
COPY RPackages.R /app/RPackages.R

# ---------------------
# Install Python dependencies
# ---------------------
# Download dependencies as a separate step to take advantage of Docker's caching.
# Leverage a cache mount to /root/.cache/pip to speed up subsequent builds.
# Leverage a bind mount to requirements.txt to avoid having to copy them into
# into this layer.

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    python3 -m pip install --break-system-packages --ignore-installed -r requirements.txt
    

# Switch to the non-privileged user to run the application.
USER appuser

# Copy the source code into the container.
COPY . .

# Expose the port that the application listens on.
EXPOSE 8080

# Run the application.
CMD ["python3", "BERNARD.py", "bernard_test_cfg.txt", "INPUTS"]

# on Mac:
# uasic@Mac ~ % python3 /Users/uasic/Desktop/src/BERNARD.py /Users/uasic/Desktop/bernard_test_cfg.txt /Users/uasic/Desktop/INPUTS