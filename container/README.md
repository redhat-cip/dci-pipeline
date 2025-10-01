# Container for dci-pipeline and DCI OpenShift agents

This is an experiment to provide dci-pipeline and the DCI OpenShift
agents inside a single container.

## How to build the container

Extract all these git repositories in the same directory:

* ansible-collection-community-crypto
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

To run `dci-pipeline` from the container,
use the `-podman` wrappers like:

```ShellSession
$ ./container/dci-pipeline-podman <dci-pipeline args>
```

## Mount extra directories

By default, only $HOME is mounted in the container, you can define
the variable CONTAINER_MOUNTED_PATHS in the ~/.config/dci-pipeline/config
configuration file to mount more directories.

Example:
```ShellSession
CONTAINER_MOUNTED_PATHS=(
    "/var/lib/dci"
    "/opt/cache"
)
```
