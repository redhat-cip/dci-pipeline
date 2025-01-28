FROM registry.access.redhat.com/ubi9/ubi

LABEL name="dci-pipeline"
# keep in sync with setup.py and dci-pipeline.spec
LABEL version="0.9.0"
LABEL maintainer="DCI Team <distributed-ci@redhat.com>"

ENV LANG en_US.UTF-8

# hadolint ignore=DL3020
ADD dist/* /usr/src/

RUN set -ex && \
    dnf -y update && \
    dnf -y install git gcc gettext python3-devel python3-pip python3-setuptools python3-cryptography \
        python3-netaddr make sudo policycoreutils fuse-overlayfs wget podman jq && \
    dnf -y install https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm && \
    dnf -y install python3-openshift python3-passlib && \
    mkdir -p /usr/share/dci /usr/share/ansible/roles /etc/ansible/roles /usr/share/ansible/collections && \
    export ANSIBLE_ROLES_PATH=/usr/share/ansible/roles:/etc/ansible/roles && \
    export ANSIBLE_COLLECTIONS_PATHS=/usr/share/ansible/collections && \
    LANG=C ANSIBLE_DIR="/usr/share/dci/" /usr/src/dci-pipeline-*/container/install-from-source.sh && \
    cd /usr/src/dci-ansible* && cp -r modules module_utils callback action_plugins filter_plugins /usr/share/dci/ && \
    adduser --home /var/lib/dci-openshift-agent dci-openshift-agent && \
    chown -R dci-openshift-agent: /var/lib/dci-openshift-agent && \
    sed -i 's/^#\s*\(%wheel\s\+ALL=(ALL)\s\+NOPASSWD:\s\+ALL\)/\1/' /etc/sudoers && \
    rm -rf /var/cache /var/log/dnf* /var/log/yum.* && \
    rm -rf /usr/src/* ~/.cache && \
    dnf clean all

ARG _REPO_URL="https://raw.githubusercontent.com/containers/image_build/main/podman"
# hadolint ignore=DL3020
ADD $_REPO_URL/containers.conf /etc/containers/containers.conf

RUN sed -i -e 's|^#mount_program|mount_program|g' \
           -e '/additionalimage.*/a "/var/lib/shared",' \
           -e 's|^mountopt[[:space:]]*=.*$|mountopt = "nodev,fsync=0"|g' \
           /etc/containers/storage.conf

VOLUME /var/lib/containers

RUN mkdir -p /var/lib/shared/overlay-images \
             /var/lib/shared/overlay-layers \
             /var/lib/shared/vfs-images \
             /var/lib/shared/vfs-layers && \
    touch /var/lib/shared/overlay-images/images.lock &&\
    touch /var/lib/shared/overlay-layers/layers.lock && \
    touch /var/lib/shared/vfs-images/images.lock && \
    touch /var/lib/shared/vfs-layers/layers.lock
