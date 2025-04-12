FROM smartgic/ovos-base:latest

ARG ALPHA=true
ARG USER=ovos

USER root

# Clone and install the app
COPY . /tmp/ovos-yaml-editor
RUN pip install /tmp/ovos-yaml-editor

USER "$USER"

WORKDIR "/home/${USER}"

# Expose port
EXPOSE 9200

# Command to run the web UI
CMD ["ovos-yaml-editor", "--host=0.0.0.0", "--port=9200"]


