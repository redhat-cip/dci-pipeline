FROM registry.access.redhat.com/ubi9/ubi

LABEL name="dci-pipeline"
# keep in sync with setup.py and dci-pipeline.spec
LABEL version="0.1.0"
LABEL maintainer="DCI Team <distributed-ci@redhat.com>"

ENV LANG en_US.UTF-8

ADD dist/* /usr/src/

RUN set -ex && \
    dnf -y install --disableplugin=subscription-manager git python3-devel python3-pip python3-setuptools python3-cryptography  make && \
    dnf upgrade -y --disableplugin=subscription-manager && \
    dnf clean all && \
    mkdir -p /usr/share/dci /usr/share/ansible/roles /etc/ansible/roles /usr/share/ansible/collections && \
    export ANSIBLE_ROLES_PATH=/usr/share/ansible/roles:/etc/ansible/roles && \
    export ANSIBLE_COLLECTIONS_PATHS=/usr/share/ansible/collections && \
    /usr/src/dci-pipeline-*/container/install-from-source.sh && \
    cd /usr/src/dci-ansible* && cp -r modules module_utils callback action_plugins filter_plugins /usr/share/dci/ && \
    rm -rf /usr/src/* ~/.cache
