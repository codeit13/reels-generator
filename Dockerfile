FROM python:3.11-slim AS builder

WORKDIR /app

# ARG DOPPLER_TOKEN
# ENV DOPPLER_TOKEN=${DOPPLER_TOKEN}

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    software-properties-common \
    git \
    imagemagick \
    ffmpeg \ 
    && rm -rf /var/lib/apt/lists/*

# REMOVE DOPPLER CLI INSTALLATION
# RUN apt-get update && apt-get install -y apt-transport-https ca-certificates curl gnupg && \
#     curl -sLf --retry 3 --tlsv1.2 --proto "=https" 'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' | gpg --dearmor -o /usr/share/keyrings/doppler-archive-keyring.gpg && \
#     echo "deb [signed-by=/usr/share/keyrings/doppler-archive-keyring.gpg] https://packages.doppler.com/public/cli/deb/debian any-version main" | tee /etc/apt/sources.list.d/doppler-cli.list && \
#     apt-get update && \
#     apt-get -y install doppler

# Set environment variables for PyDub and MoviePy to find FFmpeg
ENV FFMPEG_BINARY=/usr/bin/ffmpeg
ENV PATH="/usr/bin:${PATH}"

RUN cat /etc/ImageMagick-6/policy.xml | sed 's/none/read,write/g'> /etc/ImageMagick-6/policy.xml

COPY . .

RUN pip install poetry

RUN poetry config virtualenvs.create false

# Verify FFmpeg installation
RUN ffmpeg -version
RUN which ffmpeg

# First, try to install the Git-based MoviePy separately
RUN pip install git+https://github.com/Zulko/moviepy.git

# Then install all dependencies without any group exclusions
RUN poetry install --no-root --no-interaction --no-ansi

# Download and install the spaCy language model
RUN python -m spacy download en_core_web_sm

EXPOSE 7501

HEALTHCHECK CMD curl --fail http://localhost:7501/_stcore/health

# ENTRYPOINT [ "doppler", "run", "--"]
# docker-compose build --build-arg DOPPLER_TOKEN=dummy-token
# docker-compose up
CMD ["python", "-m", "streamlit", "run", "reelsmaker.py", "--server.port=7501", "--server.address=0.0.0.0"]
