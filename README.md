# CI pipeline management for DCI jobs

## Installation

To install dci-pipeline on a RHEL 8 system, do the following as root:

```ShellSession
# dnf install -y https://packages.distributed-ci.io/dci-release.el8.noarch.rpm
# cat > /etc/yum.repos.d/ansible-runner.repo <<EOF
[ansible-runner]
name=Ansible Runner for EL 8 - $basearch
baseurl=https://releases.ansible.com/ansible-runner/rpm/epel-8-x86_64/
enabled=1
gpgcheck=1
gpgkey=https://releases.ansible.com/keys/RPM-GPG-KEY-ansible-release.pub
EOF
# dnf install -y dci-pipeline
```

### Folders and files location

Once `dci-pipeline` package is installed, the files and resources you can find in this repository will be placed in the following locations:

- `/etc/dci-pipeline` only contains an empty `pipeline.yml` file.
- `/etc/sysconfig` folder contains the content of `sysconfig` folder, which is `dci-pipeline` file.
- `/etc/bash_completion.d` contains a `dci-queue` file related to this tool, which comes from `dciqueue/dci-queue.bash_completion` file.
- `/usr/share/dci-pipeline` contains the following scripts from `tools` folder in this repo: `alert`, `common`, `dci-pipeline-helper`, `extract-dependencies`, `get-config-entry`, `loop_until_failure`, `loop_until_success`, `send_status`, `send_comment`, `test-runner` and `yaml2json`. If `podman` flavour is selected, then `<script>-podman` scripts are placed here too.
- `/usr/bin` folder holds scripts such as `dci-pipeline`, `dci-auto-launch`, `dci-pipeline-schedule`, `dci-pipeline-check`, `dci-queue`, `dci-agent-ctl`, `dci-rebuild-pipeline`, `dci-settings2pipeline` and `dci-diff-pipeline`. If `podman` flavour is selected, then `<script>-podman` scripts are placed here too. Note that some of these scripts come from `tools` folder, and others are generated from folders like `dciagent`, `dcipipeline` or `dciqueue`, and their podman flavours are located in `container` folder.

Also, have in mind that:

- `dci-pipeline` user (with sudo permissions) and group are created. There's also a group for `dci-queue`.
- Files under `systemd` folder in this repo will be used to create the corresponding system service for `dci-pipeline`.

## dci-pipeline command

The `dci-pipeline` command allows to execute multiple DCI jobs using
different credentials. Jobs are grouped by stage. Each stage must
complete successfully before the next stage is started. The jobs with
their stages are described in YAML files that are passed to the
`dci-pipeline` command line. For example:

```ShellSession
$ dci-pipeline dcipipeline/pipeline.yml
...
$ dci-pipeline dcipipeline/pipeline-retry.yml dcipipeline/cnf-pipeline.yml
...
```

Here is a pipeline example:

```YAML
  - name: openshift-vanilla
    stage: ocp
    ansible_playbook: /usr/share/dci-openshift-agent/dci-openshift-agent.yml
    ansible_inventory: ~/inventories/agent.yml
    dci_credentials: ~/.config/dci-pipeline/dci_credentials.yml
    topic: OCP-4.14
    components:
      - ocp?tags:build:ga&name:4.14.1
      - plugin=1.1.1
```

Pipeline jobs can be split in multiple files to ease re-usability. To
do so the pipeline names must be identical in the 2 files and the
files must be loaded in order.

Example:

```YAML
  - name: openshift-vanilla
    stage: ocp
    ansible_playbook: /usr/share/dci-openshift-agent/dci-openshift-agent.yml
    ansible_inventory: ~/inventories/agent.yml
    dci_credentials: ~/.config/dci-pipeline/dci_credentials.yml
    topic: OCP-4.14
    components:
      - ocp?tags%3abuild%3aga&name:4.14.1
```

and the next file could be like that to have same result as the first
pipeline example:

```YAML
  - name: openshift-vanilla
    components:
      - plugin=1.1.1
```

### Select components with wildcards

This feature allows to select a component from one of its fields using wildcards. For example, to select using a prefix:

```YAML
  - name: openshift-vanilla
  components:
    - "repo?name:Microshift 4.14*"
```

### Schedule components by priority tags and age

this feature allows to select more precisely the components based on their tags and their age. Here is an example:

```YAML
  - name: openshift-vanilla
  components:
    - type: ocp
      priority_tags:
        - build:ga
        - build:rc
        - build:dev
        - build:nightly
      max_age: 1
```

- `type` the component type as usual
- `max_age` variable indicates the maximum age the component in term of days
- `priority_tags` this is the list of tags ordered by priority

### Changing settings from the command line

Any part in the pipeline files can be overridden on the command line
using the syntax `<job name>:<field>=<value>`. For example if you want
to change the playbook to use in the `openshift-vanilla` job from the
previous example, use:

```ShellSession
$ dci-pipeline openshift-vanilla:ansible_playbook=/tmp/myplaybook.yml ~/pipelines/ocp-vanilla-pipeline.yml
...
```

### Changing the name of the pipeline

To change the name of the pipeline, you can use the special setting
`@pipeline:name=<pipeline name>`. For example:

```ShellSession
$ dci-pipeline @pipeline:name=mypipeline mypipeline.yml
...
```

### Setting the id of the pipeline (advanced)

To set the id of the pipeline, you can use the special setting
`@pipeline:pipeline_id=<pipeline id>`. For example:

```ShellSession
$ dci-pipeline @pipeline:pipeline_id=$PIPELINE_ID mypipeline.yml
...
```

It can be useful if you want to reconnect an existing pipeline. You should also set the `previous_job_id` of your first job to be connected at the right job in the previous pipeline.

### Dynamic inventory (advanced)

If you need to create the inventory dynamically, you can use the `inventory_playbook` to generate the inventory. For example:

```YAML
  - name: openshift-vanilla
    stage: ocp
    ansible_playbook: /usr/share/dci-openshift-agent/dci-openshift-agent.yml
    inventory_playbook: ~/config/inventory.yml
    dci_credentials: ~/.config/dci-pipeline/dci_credentials.yml
    ansible_inventory: ~/inventories/agent.yml
    extra_vars:
      my_var: my_value
    topic: OCP-4.14
    components:
      - ocp
```

The `inventory_playbook` is called before the `ansible_playbook` without inventory so it can only be used to create the inventory file from the localhost. The `inventory_playbook` is called with the `extra_vars`, the `ansible_inventory` variable and, the DCI job information. Its output is visible in the DCI job output.

### Calling ansible-playbook sub commands (advanced)

If you need to call the `ansible-playbook` command in your own playbook, the tasks will be captured automatically by the DCI callback mechanism. If you need to get the `extra_vars` defined in the job definition or passed on the command line of `dci-pipeline`, you can use the `DCI_PLAYBOOK_ARGS` environment variable. Example:

```YAML
    - name: "Start VM and generate inventory"
      ansible.builtin.shell: |
        set -eux -o pipefail
        ansible-playbook $DCI_PLAYBOOK_ARGS {{ samples_dir }}/ocp_on_libvirt/libvirt_up.yml -i {{ inventory_dir }}
        ...
```

### Directory

`dci-pipeline` runs the jobs in their own workspace in
`/var/lib/dci-pipeline/<job name>/<job id>`. Various log files are
saved in this directory to ease debugging the DCI jobs.

### Sharing information between jobs

The only way to share information between jobs is to use the
output/input mechanism. This mechanism allows a job to export a file
and have another job make use of this exported file.

For example, a first job will export a `kubeconfig` file:

```YAML
  - name: openshift-vanilla
    stage: ocp
    ansible_playbook: /usr/share/dci-openshift-agent/dci-openshift-agent.yml
    ansible_inventory: ~/inventories/agent.yml
    dci_credentials: ~/.config/dci-pipeline/dci_credentials.yml
    topic: OCP-4.14
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
field to specify the stages or names of the previous jobs to lookup for
a corresponding `outputs` like this:

```YAML
- name: example-cnf
  stage: cnf
  prev_stages: [ocp]
  ansible_playbook: /usr/share/dci-openshift-app-agent/dci-openshift-app-agent.yml
  dci_credentials: /etc/dci-openshift-app-agent/dci_credentials.yml
  topic: OCP-4.14
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

### Tagging and retrying

`dci-pipeline` can tag components on successful jobs by specifying a
`success_tag` in the job definition. Example:

```YAML
  - name: openshift-vanilla
    stage: ocp
    ansible_playbook: /usr/share/dci-openshift-agent/dci-openshift-agent.yml
    ansible_inventory: ~/inventories/agent.yml
    dci_credentials: ~/.config/dci-pipeline/dci_credentials.yml
    topic: OCP-4.14
    components:
      - ocp
    success_tag: ocp-vanilla-4.14-ok
```

If you want the job to restart on failure to the last known good
components, you can specify `fallback_last_success` to lookup
components with these tags. This is useful to be sure to have a
successful job for a group even when a new delivery is broken to
continue testing the next layers in the pipeline. Example:

```YAML
  - name: openshift-vanilla
    stage: ocp
    ansible_playbook: /usr/share/dci-openshift-agent/dci-openshift-agent.yml
    ansible_inventory: ~/inventories/agent.yml
    dci_credentials: ~/.config/dci-pipeline/dci_credentials.yml
    topic: OCP-4.14
    components:
      - ocp
      - cnf
    success_tag: ocp-vanilla-4.14-ok
    fallback_last_success:
      - ocp-vanilla-4.14-ok
      - ocp?build:ga
```

In this example, when a fallback happens, `dci-pipeline` looks up the `ocp-vanilla-4.14-ok` and `build:ga` tags for the `ocp` component and only the `ocp-vanilla-4.14-ok` tag for the `cnf` component.

### Passing environment variables

If you want to pass environment variables to the agent. Example:

```YAML
  - name: openshift-vanilla
    stage: ocp
    ansible_playbook: /usr/share/dci-openshift-agent/dci-openshift-agent.yml
    ansible_inventory: ~/inventories/agent.yml
    ansible_extravars:
      answer: 42
    ansible_envvars:
      ENVVAR_42: 42
      ENVVAR_43: 43
    dci_credentials: ~/.config/dci-pipeline/dci_credentials.yml
    topic: OCP-4.14
    components:
      - ocp
    success_tag: ocp-vanilla-4.14-ok
    fallback_last_success: ocp-vanilla-4.14-ok
```

### Instrument the pipeline with temporary directories

You can specify the meta value "/@tmpdir" that will be replaced
by an actual path of a temporary directory. Example:

```YAML
  - name: openshift-vanilla
    stage: ocp
    ansible_playbook: /usr/share/dci-openshift-agent/dci-openshift-agent.yml
    ansible_inventory: ~/inventories/agent.yml
    ansible_extravars:
      answer: 42
    ansible_envvars:
      ENVVAR_42: 42
      ENVVAR_43: 43
      MY_TMP_DIR: /@tmpdir
    dci_credentials: ~/.config/dci-pipeline/dci_credentials.yml
    topic: OCP-4.14
    components:
      - ocp
    success_tag: ocp-vanilla-4.14-ok
    fallback_last_success: ocp-vanilla-4.14-ok
```

This will create a new temporary directory before running the job, at the end of
the job the directory is removed.

### Special environment variables

`dci-pipeline` is setting the following environment variables to
enable the `junit` Ansible callback to work out of the box:

```YAML
  ansible_envvars:
      JUNIT_TEST_CASE_PREFIX: test_
      JUNIT_TASK_CLASS: yes
      JUNIT_OUTPUT_DIR: /@tmpdir
```

You can override them if you need.

### Using Ansible variable files

You can specify extra Ansible variable files using the
`ansible_extravars_files` key in your pipeline file. Example:

```YAML
  - name: openshift-vanilla
    stage: ocp
    ansible_playbook: /usr/share/dci-openshift-agent/dci-openshift-agent.yml
    ansible_inventory: ~/inventories/cluster.yml
    ansible_extravars_files:
      - agents/openshift-vanilla/vars.yml
    dci_credentials: ~/.config/dci-pipeline/dci_credentials.yml
    topic: OCP-4.14
    components:
      - ocp
```

### Feeding variables from the command line

You can feed variables from the command line to the `dci-pipeline-schedule` and `dci-pipeline-check` commands that we explain below.

Variables set this way take the highest precedence and override those set in the pipeline definition files.

Each variable is set with a string of the format:

```<jobdef name>:<key>=<value>```

Where:

- **jobdef name:** is the name set in the pipeline stage definition.

- **key:** is the top name of the stage variable you are overriding. For instance: *topic* or *components*.

- **value:** is the value you want to set.

On the other hand, several formats are accepted for the value that will be handled differently:

- **`<jobdef name>:<key>=<value>`** just a literal text string. For instance, when defining the topic.

- **`<jobdef name>:<key>=<value1>,<value2>,...`** a command-separated list of values with no blank spaces between items is parsed as a string. To define a one element list, the value must be followed by a comma, even if there's not second element. For instance, when defining more than one variables file.

- **`<jobdef name>:<key>=<subkey>:<value>`** a value comprising two strings separated by a colon is parsed as a dictionary with a subkey and a value. If the subkey already exists in the pipeline manifest, it is overridden. If it does not exists, the subkey is added under the key, so any other subkey already existing is kept. For instance, when defining the components.

- **`<jobdef name>:<key>='{"json":"string"}'`** a value formatted as a json text string is parsed as such resulting in a composite object. In this case, surrounding the json string or the entire parameter with single quotes is mandatory or the shell interpreter may try to apply [brace expansion](https://www.gnu.org/software/bash/manual/html_node/Brace-Expansion.html), thus breaking the json formatting.

The following is a usage example:

```ShellSession
$ dci-pipeline-schedule ocp-vanilla workload \
    ocp-vanilla:topic=OCP-4.14 \
    workload:components=operator1,operator2 \
    workload:ansible_extravars=dci_tags:example \
    workload:ansible_extravars='{"user":"jdoe","password":"Pass123$"}'
...
```

### Previous Topic

In a multi-stage pipeline, you can inherit the `topic` from the
previous stage by using `use_previous_topic` in the
configuration of the job. Example:

```YAML
  - name: workload
    stage: app
    ansible_playbook: /usr/share/dci-openshift-app-agent/dci-openshift-app-agent.yml
    ansible_inventory: ~/inventories/app.yml
    dci_credentials: ~/.config/dci-pipeline/dci_credentials.yml
    use_previous_topic: true
```

## dci-pipeline-schedule

`dci-pipeline-schedule` is a wrapper to call `dci-pipeline` without
specifying the paths for the pipeline files and the inventories. This
allows to have a more concise syntax.

For example, to do the equivalent of:

```ShellSession
$ dci-pipeline ~/pipelines/ocp-vanilla-pipeline.yml ~/pipelines/workload-pipeline.yml
...
```

Use:

```ShellSession
$ dci-pipeline-schedule ocp-vanilla workload
...
```

For this to work, you need to configure `PIPELINES_DIR` in one these
files: `~/.config/dci-pipeline/config` or
`/etc/dci-pipeline/config`. Example:

```Shell
PIPELINES_DIR=~/my-config-dir/pipelines
```

You can also define the default `dci-queue` queue with the
`DEFAULT_QUEUE` variable. To schedule on a specific `dci-queue` pool,
use `-p` like this:

```ShellSession
$ dci-pipeline-schedule -p my-pool ocp-vanilla workload
...
```

## dci-pipeline-check

To test a Github PR, with specific a pipeline you can use
`dci-pipeline-check` utility like that:

```ShellSession
$ dci-pipeline-check https://github.com/dci-labs/pipelines/pull/6 -p my-pool ocp-4.14-vanilla workload
```

If you use private GitHub repositories, you need to set the
`GITHUB_TOKEN` variable in your configuration file to get the details
using the GitHub API about the changes. Then you need either to set
the `GITHUB_SSH_ID` variable to download the pull request using `ssh` or the
`GITHUB_LOGIN` variable to use `https`. The ssh key needs to be
without password for the automation to work.

For dci-pipeline-check to vote like a regular CI system on GitHub, set
the variable `GITHUB_VOTING_REPOS` to a regexp matching the
repositories you want to vote on in your configuratio file. Your GitHub
token needs the rights to vote for this to work. If you don't want to
have comments in Github, use the variable `GITHUB_NO_COMMENT_REPOS` as
a regexp for the projects where you don't want to receive comments.

If you use multiple Github accounts for different Github projects, you
can use the `~/.config/dci-pipeline/config.yaml` or
`/etc/dci-pipeline/config.yaml` files to define your specific
configuration. Example:

```YAML
https://github.com/org/proj:
    github_token: mytoken
    github_login: mylogin
    github_ssh_id: myid
    git_clone_options: myoption
```

It also works for a Gerrit review from <https://softwarefactory-project.io/r> :

```ShellSession
$ dci-pipeline-check 19837 -p my-pool ocp-4.14-vanilla workload
```

To vote on Gerrit reviews, you need to set the `GERRIT_SSH_ID` to
point to the ssh key name (key without password) and the
`GERRIT_SSH_LOGIN` variables.

`dci-pipeline-check` uses the same configuration files as `dci-pipeline-schedule`.

If no DCI job has been created by `dci-pipeline-check`, it stores its
working directory into `/tmp/test-runner-$DATE-$ID` to ease the debug
later.

### Testing on an existing OCP cluster

To test a change on the `dci-openshift-app-agent` without
re-installing an OCP cluster, you need to pass an extra parameter to
the `dci-pipeline-check` command pointng to the `KUBECONFIG` of the
OCP cluster like this:

```ShellSession
$ dci-pipeline-check 26269 /path/to/kubeconfig workload
```

This bypasses the queue mechanism and directly launches the
application pipelines on the OCP cluster.

### Dependencies between changes

Sometimes you also need multiple changes to be tested at the same
time. To do so, add a `Build-Depends` or `Depends-On` field pointing
to you GitHub PR or Gerrit review in your git commit or GitHub PR
description like this:

```Text
Build-Depends: https://github.com/dci-labs/pipelines/pull/1
Depends-On: https://softwarefactory-project.io/r/c/dci-jobs/+/29071
```

See this example: <https://softwarefactory-project.io/r/c/dci-pipeline/+/26189>

### dci-auto-launch

`dci-auto-launch` allows to automatically schedule pipelines based
on strings in the description of the pull request or gerrit review. It
is meant to be used on the stream of events from Github or Gerrit.

It relies on the configuration file `~/.config/dci-pipeline/auto.conf` in the following format:

```ini
[Lab]
cmd = dci-pipeline-check @URL -p pool

[Workload]
cmd = dci-queue schedule wrkld -- env QUEUE_TOKEN=@RESOURCE dci-pipeline-check @URL -p cluster /path/to/kubeconfig
```

And then you can use a string like that in the description of the change:

```Text
TestLab: ocp-vanilla
TestWorkload: workload
```

That will schedule the pipelines `ocp-vanilla` and `workload` like this:

```ShellSession
$ dci-pipeline-check <change URL> -p pool ocp-vanilla
$ dci-queue schedule wrkld -- env QUEUE_TOKEN=@RESOURCE dci-pipeline-check <change URL> -p cluster /path/to/kubeconfig workload
```

### no-check and force-check

You can also specify a `Test-Hint:` field in the description of your
change. This will direct `dci-pipeline-check` to test in a specific way:

- `Test-Hint: no-check` do not run a check (useful in CI mode).
- `Test-Hint: force-check` run a check even if there is no code change (useful in CI mode).

## Link between dci-pipeline and dci-queue: @QUEUE and @RESOURCE

`dci-pipeline-schedule` and `dci-pipeline-check` are the links between `dci-queue` and `dci-pipeline`. These utilities are substituting the strings `@QUEUE` and `@RESOURCE` coming from `dci-queue` in the inventory path, the configuration, and the ansible_extravars of the `dci-pipeline` job definitions. Example:

```YAML
  - name: workload
    stage: app
    ansible_playbook: /usr/share/dci-openshift-app-agent/dci-openshift-app-agent.yml
    ansible_inventory: ~/inventories/@QUEUE/@RESOURCE.yml
    configuration: "@QUEUE"
    ansible_extravars:
      custom_config: /path/to/config/for/@QUEUE/@RESOURCE-config.yml
    ...
```

`dci-pipeline-schedule` and `dci-pipeline-check` are also managing the `topic` of jobs if there are only `dci-openshift-app-agent` job definitions without any `dci-openshift-agent` job definitions in the pipeline. To do so they rely on the running cluster defined by the `KUBECONFIG` environment variable or the ansible variable `kubeconfig_path` defined either in the job definition or in the inventory (`all.vars.kubeconfig_path`). Then they deduce the topic of the job from the OpenShift version of the cluster.

## dci-agent-ctl

`dci-agent-ctl` is thin layer on top of `dci-pipeline` to consume regular
agent settings transparently.

```ShellSession
$ dci-agent-ctl /etc/dci-openshift-agent/settings.yml /etc/dci-openshift-app-agent/settings.yml
```

will translate the settings in `/etc/dci-openshift-agent/settings.yml`
and `/etc/dci-openshift-app-agent/settings.yml` into pipelines and
call `dci-pipeline` on them.

to be compatible with `dci-agent-ctl`, `setting.yml` files must have the
following fields:

```YAML
dci_name: "<job-name-no-space>"
dci_agent: openshift
```

`dci_agent` is the name of the agent: `rhel`, `openstack`, `openshift`
or `openshift-app`.

By default, the DCI credentials will be taken from the same location
as the `settings.yml` file in a YAML file called
`dci_credentials.yml`. The format must be following:

```YAML
  DCI_CLIENT_ID: <remote ci id>
  DCI_API_SECRET: <remote ci secret>
  DCI_CS_URL: https://api.distributed-ci.io/
```

The path to this file can be overridden in the `settings.yml` files like:

```YAML
dci_name: "<job-name-no-space>"
dci_agent: openshift
dci_credentials: "/etc/dci/dci_credentials.yml"
```

### dci-settings2pipeline

To use the parsing capabilities of `dci-agent-ctl` and just output the
pipeline file without executing `dci-pipeline`, use
`dci-settings2pipeline` like this:

```ShellSession
$ dci-settings2pipeline /etc/dci-openshift-agent/settings.yml /etc/dci-openshift-app-agent/settings.yml /tmp/pipelines.yml
```

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

List pools in the host

```ShellSession
$ dci-queue list
The following pools were found:
  8nodes
Run the command below for the list of commands scheduled on your target pool:
  dci-queue list <pool>
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

The following environment variables are set when running a job:

- DCI\_QUEUE: name of the pool.
- DCI\_QUEUE\_ID: id of the job.
- DCI\_QUEUE\_JOBID: uniq id with &lt;pool name&gt;.&lt;id of the job&gt;

You can unschedule the command `1` from the pool `8nodes`:

```ShellSession
$ dci-queue unschedule 8nodes 1
```

Remove `cluster4` from available resources in the `8nodes` pool:

```ShellSession
$ dci-queue remove-resource 8nodes cluster4 'reserved to debug blabla (fred)'
```

You can also force the removal of a resource with `dci-queue remove-resource -f`, so that the resource will no
longer be available in the pool (you will need to reinclude it with `dci-queue add-resource` command). Example
with `cluster6`:

```ShellSession
$ dci-queue remove-resource -f 8nodes cluster6 'whatever reason'
```

Remove the `8nodes` pool:

```ShellSession
$ dci-queue remove-pool 8nodes
```

### Interactions with dci-pipeline-check and dci-pipeline-schedule

When `dci-pipeline-check` and `dci-pipeline-schedule` are used in
conjunction with `dci-queue`, they automatically schedule the commands
to run through `dci-queue`. They also perform the substitution of the
`@QUEUE` and `@RESOURCE` strings in the `ansible_inventory`, the
`configuration` and the `ansible_extravars` settings of the jobs allowing
to have flexible job definitions regarding inventories and configurations
without having to change the command lines.

## How to rebuild a pipeline

In case of a pipeline failure, one might need to rebuild the original one. The command `dci-rebuild-pipeline` can
be used for this purpose. To do so, you need to get any job id that was part of the pipeline you want to rebuild.

Once this is get. You need to run, for example, the following command:

```ShellSession
$ dci-rebuild-pipeline --job_id 2441f3a5-aa97-45e9-8122-36dfc6f17d84
```

At the end of the command you will get a file `rebuilt-pipeline.yml` in the current directory.

The rebuilt pipeline will pin the components version to the original one.

For instance instead of having this component list from the original pipeline:

```YAML
components:
  - ocp
  - ose-tests
  - cnf-tests
```

You will got:

```YAML
components:
  - ocp=ocp-4.14.0-0.nightly-20230701
  - ose-tests=ose-tests-20200628
  - cnf-tests=cnf-tests-20200628
```

This rebuilt pipeline can be used as a regular one with the `dci-pipeline` command.

If you do not specify `--job_id`, `dci-rebuild-pipeline` is using the last job that has run.

## How to see components diff between two pipelines

In case of a pipeline failulre, one might check if some components has changed from the previous run. The
command `dci-diff-pipeline` can be used for this purpose. To do so, you need to get two jobs that are part
of each pipeline (it can be any of the pipeline's job).

Once you got the two job ids, you need to use a user that has access to every components of the pipelines, including
teams components.

You can see the component differentiation with the following command:

```ShellSession
$ dci-diff-pipeline --job_id_1 610953f7-ad4a-442c-a934-cd5506127ec9 --job_id_2 f7677627-5780-46f8-b35f-c4bd1f781d90
+--------------------------------------+--------------------------------------+-------------------+------------------+--------------------------------+--------------------------------+
|              pipeline 1              |              pipeline 2              |       stage       |  component type  |          component 1           |          component 2           |
+--------------------------------------+--------------------------------------+-------------------+------------------+--------------------------------+--------------------------------+
| 94a4b04f-4aa5-413b-a86f-eb651b563e0b | ef493b57-a02e-4c74-9f60-e951b181f1d4 | openshift-vanilla |       ocp        |  ocp-4.14.0-0.nightly-20230703  |  ocp-4.14.0-0.nightly-20230701  |
| 610953f7-ad4a-442c-a934-cd5506127ec9 | f7677627-5780-46f8-b35f-c4bd1f781d90 |       rh-cnf      |      rh-cnf      |  rh-cnf-0.1.nightly-20200708   |  rh-cnf-0.1.nightly-20200703   |
+--------------------------------------+--------------------------------------+-------------------+------------------+--------------------------------+--------------------------------+
```

If you do not specify `--job_id_1`, `dci-diff-pipeline` looks up the last job.

If you do not specify `--job_id_2`, `dci-diff-pipeline` looks up the
first job from the last pipeline with the same name as the one from
`--job_id_1`.

## Development

Submit changes to <https://softwarefactory-project.io/project/Distributed-CI>

### Tests

To run the tests, you need to have `tox` installed on your system.

There are 3 kinds of tests:

- `lint`: static code checks using `flake8` and `black`.
- `unit`: runs unit tests.
- `functional`: runs functional tests against a local
  [dci-dev-env](https://github.com/redhat-cip/dci-dev-env) instance
  prepared with `dev-setup/dci-telcoprovisioning`.

### pre-commit

If you want to setup a git pre-commit hook, which verify a few checks
using <https://pre-commit.com/> before accepting a commit, do the following:

```ShellSession
$ tox -epre-commit
```
