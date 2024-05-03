# Container for dci-pipeline and DCI OpenShift agents

This is an experiment to provide dci-pipeline and the DCI OpenShift
agents inside a single container.

## How to build the container

Extract all these git repositories in the same directory:

* ansible-collection-community-crypto
* ansible-collection-community-kubernetes
* ansible-collection-community-general
* ansible-collection-community-libvirt
* ansible-collection-containers-podman
* ansible-role-dci-podman
* ansible-role-dci-sync-registry
* dci-ansible
* dci-openshift-agent
* dci-openshift-app-agent
* dci-pipeline
* python-dciauth
* python-dciclient

Then run the following command to build the container:

```ShellSession
$ cd dci-pipeline
$ ./container/build.sh
```

## How to use the container

To run `dci-pipeline` or `dci-openshift-agent-ctl` from the container,
use the `-podman` wrappers like:

```ShellSession
$ ./container/dci-pipeline-podman <dci-pipeline args>
...
$ ./container/dci-openshift-agent-ctl-podman <dci-openshift-agent-ctl args>
...
```
