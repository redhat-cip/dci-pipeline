# CI pipeline management for DCI jobs

## dci-pipeline command

## queue command

The `queue` command allows to execute commands consuming resources
from pools.

Create a pool named `8nodes`:
```
$ queue add-pool 8nodes
```

Add resources `cluster4` and `cluster6` into the `8nodes` pool:
```
$ queue add-resource 8nodes cluster4
$ queue add-resource 8nodes cluster6
```

Schedule a dci-pipeline command on the `8nodes` pool:
```
$ queue schedule 8nodes dci-pipeline openshift-vanilla:ansible_inventory=/etc/inventories/@RESOURCE pipeline.yml
```

The `@RESOURCE` is mandatory in the command line to be executed and it
is replaced by the resource name at execution time.

Schedule a dci-pipeline command on the `8nodes` pool waiting for the
command to complete to have its exit code and having all the log on the
console:
```
$ queue -c -l DEBUG schedule -b 8nodes dci-pipeline openshift-vanilla:ansible_inventory=/etc/inventories/@RESOURCE pipeline.yml
```

List queue:
```
$ queue list 8nodes
Commands on the 8nodes pool:
1: dci-pipeline openshift-vanilla:ansible_inventory=/etc/inventories/@RESOURCE pipeline.yml (wd: /home/dci-pipeline)
```

Run commands from a pool (using all the available resources):
```
$ queue run 8nodes
```

Remove resource `cluster4` from the `8nodes` pool:
```
$ queue remove-resource 8nodes cluster4
```

Remove the `8nodes` pool:
```
$ queue remove-pool 8nodes
```
