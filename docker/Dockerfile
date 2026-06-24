# docker/Dockerfile
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System dependencies + OPM PPA
RUN apt-get update && \
    apt-get install -y software-properties-common curl git wget && \
    add-apt-repository -y ppa:opm/ppa && \
    apt-get update && \
    apt-get install -y \
        mpi-default-bin \
        libopm-simulators-bin \
        python3-opm-common \
        python3-opm-simulators \
        resinsight \
        python3-pip \
        python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# App
WORKDIR /app
COPY . /app

EXPOSE 8501

CMD ["streamlit", "run", "opm_ai/chat/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0"]
