FROM python:3.6

LABEL name="dci-pipeline"
# keep in sync with setup.py and dci-pipeline.spec
LABEL version="0.1.0"
LABEL maintainer="DCI Team <distributed-ci@redhat.com>"

ADD dist/* /usr/src/

RUN set -ex && \
    mkdir -p /usr/share/dci /usr/share/ansible/roles /etc/ansible/roles /usr/share/ansible/collections && \
    export ANSIBLE_ROLES_PATH=/usr/share/ansible/roles:/etc/ansible/roles && \
    export ANSIBLE_COLLECTIONS_PATHS=/usr/share/ansible/collections && \
    /usr/src/dci-pipeline-*/container/install-from-source.sh && \
    cd /usr/src/dci-ansible* && cp -r modules module_utils callback action_plugins filter_plugins /usr/share/dci/ && \
    rm -rf /usr/src/* ~/.cache
