# CI pipeline management for DCI jobs

## dci-pipeline command

The `dci-pipeline` command allows to execute multiple DCI jobs using
different credentials. Jobs are grouped by type. Each group must
complete successfully before the next group is started. The jobs with
their types are described in YAML files that are passed to the
`dci-pipeline` command line. For example:

```ShellSession
$ dci-pipeline dcipipeline/pipeline.yml
$ dci-pipeline dcipipeline/pipeline-retry.yml dcipipeline/cnf-pipeline.yml
```

Here is a pipeline example:
```YAML
---
  - name: openshift-vanilla
    type: ocp
    ansible_playbook: /usr/share/dci-openshift-agent/dci-openshift-agent.yml
    ansible_inventory: /etc/dci-pipeline/inventory
    dci_credentials: /etc/dci-openshift-agent/dci_credentials.yml
    topic: OCP-4.5
    components:
      - ocp?tags:build:ga&name:4.5.41
      - plugin=1.1.1
```

Any part in the pipeline files can be overridden on the command line
using the syntax `<job name>:<field>=<value>`. For example if you want
to change the playbook to use in the `openshift-vanilla` job from the
previous example, use:

```ShellSession
$ dci-pipeline openshift-vanilla:ansible_playbook=/tmp/myplaybook.yml mypipeline.yml
```

`dci-pipeline` runs the jobs in their own workspace in
`/var/lib/dci-pipeline/<job name>/<job id>`. Various log files are
saved in this directory to ease debugging the DCI jobs.

### Sharing information between jobs

The only way to share information between jobs is to use the
output/input mechanism. This mechanism allows a job to export a file
and have another job make use of this exported file.

For example, a first job will export a `kubeconfig` file:
```YAML
---
  - name: openshift-vanilla
    type: ocp
    ansible_playbook: /usr/share/dci-openshift-agent/dci-openshift-agent.yml
    ansible_inventory: /etc/dci-pipeline/inventory
    dci_credentials: /etc/dci-openshift-agent/dci_credentials.yml
    topic: OCP-4.5
    components:
      - ocp
    outputs:
      kubecfg: "kubeconfig"
```

`dci-pipeline` will export a `job_info.outputs` dictionary with a
`kubecfg` key. Here is an example on how to use it in the
`dci-openshift-agent.yml` playbook specified in the example pipeline:
```YAML
- name: set outputs to be copied
  set_fact:
    outputs:
      kubecfg: "~/clusterconfigs/auth/kubeconfig"

- name: Copy outputs if defined
  delegate_to: "{{ groups['provisioner'][0] }}"
  fetch:
    src: "{{ outputs[item.key] }}"
    dest: "{{ item.value }}"
    flat: true
  with_dict: "{{ job_info.outputs }}"
  when: job_info.outputs is defined and job_info.outputs != None
```

Then to get the file of the `kubecfg` field from a previous job copied
into the job workspace and its path stored into the `kubeconfig_path`
variable, you have to define an `inputs` field and a `prev_stages`
field to specify the types or names of the previous jobs to lookup for
a corresponding `outputs` like this:

```YAML
- name: example-cnf
  type: cnf
  prev_stages: [ocp]
  ansible_playbook: /usr/share/dci-openshift-app-agent/dci-openshift-app-agent.yml
  dci_credentials: /etc/dci-openshift-app-agent/dci_credentials.yml
  topic: OCP-4.5
  components: []
  inputs:
    kubecfg: kubeconfig_path
```

The path of the `kubecfg` file will be copied by `dci-pipeline` in
the `kubeconfig_path` variable that is passed to the playbook. Here is
an example on how to use it:

```YAML
- name: "Check if KUBECONFIG exists"
  stat:
    path: "{{ kubeconfig_path }}"
  register: kubeconfig

- name: "Fail if kubeconfig NOT found"
  fail:
    msg: "kubeconfig not found at {{ kubeconfig_path }}"
  when: kubeconfig.stat.exists == False
```

### tagging and retrying

`dci-pipeline` can tag components on successful jobs by specifying a
`success_tag` in the job definition. Example:

```YAML
---
  - name: openshift-vanilla
    type: ocp
    ansible_playbook: /usr/share/dci-openshift-agent/dci-openshift-agent.yml
    ansible_inventory: /etc/dci-pipeline/inventory
    dci_credentials: /etc/dci-openshift-agent/dci_credentials.yml
    topic: OCP-4.5
    components:
      - ocp
    success_tag: ocp-vanilla-4.4-ok
```

If you want the job to restart on failure to the last known good
components, you can specify `fallback_last_success` to lookup
components with this tag. This is useful to be sure to have a
successful job for a group even when a new delivery is broken to
continue testing the next layers in the pipeline. Example:

```YAML
---
  - name: openshift-vanilla
    type: ocp
    ansible_playbook: /usr/share/dci-openshift-agent/dci-openshift-agent.yml
    ansible_inventory: /etc/dci-pipeline/inventory
    dci_credentials: /etc/dci-openshift-agent/dci_credentials.yml
    topic: OCP-4.5
    components:
      - ocp
    success_tag: ocp-vanilla-4.4-ok
    fallback_last_success: ocp-vanilla-4.5-ok
```

### passing environment variables

If you want to pass environment variables to the agent. Example:

```YAML
---
  - name: openshift-vanilla
    type: ocp
    ansible_playbook: agents/openshift-vanilla/agent.yml
    ansible_inventory: agents/openshift-vanilla/inventory
    ansible_extravars:
      answer: 42
    ansible_envvars:
      ENVVAR_42: 42
      ENVVAR_43: 43
    dci_credentials: /etc/dci-openshift-agent/dci_credentials.yml
    topic: OCP-4.5
    components:
      - ocp
    success_tag: ocp-vanilla-4.4-ok
    fallback_last_success: ocp-vanilla-4.5-ok
```

### instrument the pipeline with temporary directories

You can specify the meta value "/@tmpdir" that will be replaced
by an actual path of a temporary directory. Example:

```YAML
---
  - name: openshift-vanilla
    type: ocp
    ansible_playbook: agents/openshift-vanilla/agent.yml
    ansible_inventory: agents/openshift-vanilla/inventory
    ansible_extravars:
      answer: 42
    ansible_envvars:
      ENVVAR_42: 42
      ENVVAR_43: 43
      MY_TMP_DIR: /@tmpdir
    dci_credentials: /etc/dci-openshift-agent/dci_credentials.yml
    topic: OCP-4.5
    components:
      - ocp
    success_tag: ocp-vanilla-4.4-ok
    fallback_last_success: ocp-vanilla-4.5-ok
```

This will create a new temporary directory before running the stage, at the end of
the stage the directory is removed.

### special environment variables

`dci-pipeline` is setting the following environment variables to
enable the `junit` Ansible callback to work out of the box:

```YAML
  ansible_envvars:
      JUNIT_TEST_CASE_PREFIX: test_
      JUNIT_TASK_CLASS: yes
      JUNIT_OUTPUT_DIR: /@tmpdir
```

You can override them if you need.

## dci-queue command

The `dci-queue` command allows to execute commands consuming resources
from pools. These pools are specific to the user executing the
commands.

Create a pool named `8nodes`:
```ShellSession
$ dci-queue add-pool 8nodes
```

Add resources `cluster4` and `cluster6` into the `8nodes` pool:
```ShellSession
$ dci-queue add-resource 8nodes cluster4
$ dci-queue add-resource 8nodes cluster6
```

Schedule a dci-pipeline command on the `8nodes` pool at priority 1
(the highest the priority, the soonest it'll be executed):
```ShellSession
$ dci-queue schedule -p 1 8nodes dci-pipeline openshift-vanilla:ansible_inventory=/etc/inventories/@RESOURCE pipeline.yml
```

The `@RESOURCE` is mandatory in the command line to be executed and it
is replaced by the resource name at execution time.

Schedule a dci-pipeline command on the `8nodes` pool waiting for the
command to complete to have its exit code and having all the log on the
console:
```ShellSession
$ dci-queue -c -l DEBUG schedule -b 8nodes dci-pipeline openshift-vanilla:ansible_inventory=/etc/inventories/@RESOURCE pipeline.yml
```

List dci-queue:
```ShellSession
$ dci-queue list 8nodes
Commands on the 8nodes pool:
1(p1): dci-pipeline openshift-vanilla:ansible_inventory=/etc/inventories/@RESOURCE pipeline.yml (wd: /home/dci-pipeline)
```

Run commands from a pool (using all the available resources):
```ShellSession
$ dci-queue run 8nodes
```

You can unschedule the command `1` from the pool `8nodes`:
```ShellSession
$ dci-queue unschedule 8nodes 1
```

Remove resource `cluster4` from the `8nodes` pool:
```ShellSession
$ dci-queue remove-resource 8nodes cluster4 'reserved to debug blabla (fred)'
```

Remove the `8nodes` pool:
```ShellSession
$ dci-queue remove-pool 8nodes
```

## How to rebuild a pipeline

In case of a pipeline failure, one might need to rebuild the original one. The command `dci-rebuild-pipeline` can
be used for this purpose. To do so, you need to get any job id that was part of the pipeline you want to rebuild.

Once this is get. You need to run, for example, the following command:
```ShellSession
$ dci-rebuild-pipeline 2441f3a5-aa97-45e9-8122-36dfc6f17d84
```

At the end of the command you will get a file `rebuilt-pipeline.yml` in the current directory.

The rebuilt pipeline will pin the components version to the original one.

For instance instead of having this component list from the original pipeline:

```
components:
  - ocp
  - ose-tests
  - cnf-tests
```

You will got:

```
components:
  - ocp=ocp-4.4.0-0.nightly-20200701
  - ose-tests=ose-tests-20200628
  - cnf-tests=cnf-tests-20200628
```

This rebuilt pipeline can be used as a regular one with the `dci-pipeline` command.


## How to see components diff between two pipelines

In case of a pipeline failulre, one might check if some components has changed from the previous run. The
command `dci-diff-pipeline` can be used for this purpose. To do so, you need to get two jobs that are part
of each pipeline (it can be any of the pipeline's job).

Once you got the two job ids, you need to use a user that has access to every components of the pipelines, including
teams components.

You can see the component differentiation with the following command:
```ShellSession
$ dci-diff-pipeline 610953f7-ad4a-442c-a934-cd5506127ec9 f7677627-5780-46f8-b35f-c4bd1f781d90
using local development environment with dci_login: pipeline-user, dci_cs_url: http://127.0.0.1:5000
+--------------------------------------+--------------------------------------+-------------------+------------------+--------------------------------+--------------------------------+
|              pipeline 1              |              pipeline 2              |       stage       |  component type  |          component 1           |          component 2           |
+--------------------------------------+--------------------------------------+-------------------+------------------+--------------------------------+--------------------------------+
| 94a4b04f-4aa5-413b-a86f-eb651b563e0b | ef493b57-a02e-4c74-9f60-e951b181f1d4 | openshift-vanilla |       ocp        |  ocp-4.4.0-0.nightly-20200703  |  ocp-4.4.0-0.nightly-20200701  |
| 610953f7-ad4a-442c-a934-cd5506127ec9 | f7677627-5780-46f8-b35f-c4bd1f781d90 |       rh-cnf      |      rh-cnf      |  rh-cnf-0.1.nightly-20200708   |  rh-cnf-0.1.nightly-20200703   |
+--------------------------------------+--------------------------------------+-------------------+------------------+--------------------------------+--------------------------------+
```
