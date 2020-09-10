# CI pipeline management for DCI jobs

## dci-pipeline command

## dci-queue command

The `dci-queue` command allows to execute commands consuming resources
from pools.

Create a pool named `8nodes`:
```
$ dci-queue add-pool 8nodes
```

Add resources `cluster4` and `cluster6` into the `8nodes` pool:
```
$ dci-queue add-resource 8nodes cluster4
$ dci-queue add-resource 8nodes cluster6
```

Schedule a dci-pipeline command on the `8nodes` pool:
```
$ dci-queue schedule 8nodes dci-pipeline openshift-vanilla:ansible_inventory=/etc/inventories/@RESOURCE pipeline.yml
```

The `@RESOURCE` is mandatory in the command line to be executed and it
is replaced by the resource name at execution time.

Schedule a dci-pipeline command on the `8nodes` pool waiting for the
command to complete to have its exit code and having all the log on the
console:
```
$ dci-queue -c -l DEBUG schedule -b 8nodes dci-pipeline openshift-vanilla:ansible_inventory=/etc/inventories/@RESOURCE pipeline.yml
```

List dci-queue:
```
$ dci-queue list 8nodes
Commands on the 8nodes pool:
1: dci-pipeline openshift-vanilla:ansible_inventory=/etc/inventories/@RESOURCE pipeline.yml (wd: /home/dci-pipeline)
```

Run commands from a pool (using all the available resources):
```
$ dci-queue run 8nodes
```

You can unschedule the command `1` from the pool `8nodes`:
```
$ dci-queue unschedule 8nodes 1
```

Remove resource `cluster4` from the `8nodes` pool:
```
$ dci-queue remove-resource 8nodes cluster4
```

Remove the `8nodes` pool:
```
$ dci-queue remove-pool 8nodes
```
