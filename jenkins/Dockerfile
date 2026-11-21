# Jenkins controller used by the Entrega 2 pipeline.
# Official LTS image + Docker CLI/Compose plugin (to drive the host Docker daemon)
# + the plugins listed in plugins.txt.
FROM jenkins/jenkins:lts-jdk21

USER root

# Only the Docker CLI, Buildx (BuildKit, needed for Dockerfile.test.dockerignore)
# and Compose are installed (NOT the daemon):
# builds run on the host daemon through the mounted /var/run/docker.sock.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-buildx-plugin docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

USER jenkins

# Skip the interactive setup wizard: the admin user, credentials and the job are
# created by Configuration as Code (casc/jenkins.yaml).
ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false" \
    CASC_JENKINS_CONFIG=/var/jenkins_home/casc/jenkins.yaml

COPY --chown=jenkins:jenkins plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt
