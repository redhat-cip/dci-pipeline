# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Red Hat, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations

import json
import logging
import os
import shutil
import signal
import sys
import tempfile

import ansible_runner
import yaml
from ansible.cli import CLI
from ansible.parsing.ajson import AnsibleJSONEncoder
from ansible.parsing.dataloader import DataLoader
from ansible.parsing.utils.yaml import from_yaml
from ansible.parsing.yaml.dumper import AnsibleDumper
from dciclient.v1.api import component as dci_component
from dciclient.v1.api import context as dci_context
from dciclient.v1.api import file as dci_file
from dciclient.v1.api import identity as dci_identity
from dciclient.v1.api import job as dci_job
from dciclient.v1.api import jobstate as dci_jobstate
from dciclient.v1.api import pipeline as dci_pipeline
from dciclient.v1.api import topic as dci_topic

if sys.version_info[0] == 2:
    FileNotFoundError = IOError
    PermissionError = IOError

# remove all handlers before adding the console handler to avoid a
# side effect of having loaded ansible.utils.display which creates a
# logger to ANSIBLE_LOG if set in ansible.cfg.
root_logger = logging.getLogger()
del root_logger.handlers[:]
# make sure we log on stdout/stderr
log = logging.getLogger(__name__)
log_level = getattr(logging, os.getenv("DCI_PIPELINE_LOG_LEVEL", "INFO"))
console_handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
log.addHandler(console_handler)
log.setLevel(log_level)

VERBOSE_LEVEL = int(os.getenv("DCI_PIPELINE_VERBOSE_LEVEL", "2"))
TOPDIR = os.getenv(
    "DCI_PIPELINE_TOPDIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

_JOB_FINAL_STATUSES = {"error", "success", "failure", "killed"}
_JOB_PRODUCT_STATUSES = {"running"}


class SignalHandler:
    def __init__(self):
        self.signum = 0
        signal.signal(signal.SIGTERM, self._handler)
        signal.signal(signal.SIGINT, self._handler)

    def _handler(self, signum, frame):
        self.signum = signum
        log.error("Caught SIG %d" % signum)

    def called(self):
        return self.signum != 0


def pre_process_stage(stage):
    metas = {}
    if "ansible_envvars" not in stage:
        stage["ansible_envvars"] = {}

    # create sane default env variables
    if "JUNIT_TEST_CASE_PREFIX" not in stage["ansible_envvars"]:
        stage["ansible_envvars"]["JUNIT_TEST_CASE_PREFIX"] = "test_"
    if "JUNIT_TASK_CLASS" not in stage["ansible_envvars"]:
        stage["ansible_envvars"]["JUNIT_TASK_CLASS"] = "yes"
    if "JUNIT_OUTPUT_DIR" not in stage["ansible_envvars"]:
        stage["ansible_envvars"]["JUNIT_OUTPUT_DIR"] = "/@tmpdir"

    for k, v in stage["ansible_envvars"].items():
        if v != "/@tmpdir":
            continue
        stage["ansible_envvars"][k] = tempfile.mkdtemp(prefix="dci-pipeline-tmpdir")
        log.info("Created %s for env var %s" % (stage["ansible_envvars"][k], k))
        if "tmpdirs" not in metas:
            metas["tmpdirs"] = [{"name": k, "path": stage["ansible_envvars"][k]}]
        else:
            metas["tmpdirs"].append({"name": k, "path": stage["ansible_envvars"][k]})
    return metas, stage


def post_process_stage(context, stage, metas):
    if "tmpdirs" not in metas:
        return

    for tmpdir in metas["tmpdirs"]:
        if tmpdir["name"] == "JUNIT_OUTPUT_DIR":
            upload_junit_files_from_dir(context, stage, tmpdir["path"])
        try:
            shutil.rmtree(tmpdir["path"])
        except OSError as e:
            log.warning("unable to delete %s: %s" % (tmpdir, str(e)))


def upload_junit_files_from_dir(context, stage, dir):
    for f in os.listdir(dir):
        _abs_file_path = os.path.join(dir, f)
        if os.path.isfile(_abs_file_path) and f.endswith(".xml"):
            log.info("Uploading junit file: %s" % _abs_file_path)
            dci_file.create(
                context,
                f[:-4],  # remove .xml at the end
                file_path=_abs_file_path,
                mime="application/junit",
                job_id=stage["job_info"]["job"]["id"],
            )
        else:
            log.warning("%s is not a junit file" % _abs_file_path)


def clean_ansible_objects(data):
    return yaml.load(yaml.dump(data, Dumper=AnsibleDumper), Loader=yaml.BaseLoader)


def load_stage_file(path, config_dir):
    # Read the pipeline stages in 2 passes to be able to load first
    # the credentials file to be able to decrypt !vault statements in
    # the second pass.
    with open(path) as stream:
        data = stream.read(-1)
    # First pass without decrypting !vault
    stages_raw_data = yaml.load(data, Loader=yaml.BaseLoader)
    try:
        creds = load_credentials(stages_raw_data[0], config_dir)
    except (KeyError, IndexError):
        log.warning("No credentials found to decrypt vault encrypted data.")
        creds = {"DCI_API_SECRET": "fake-secret"}
    # Second pass decrypting !vault statements
    os.environ["DCI_API_SECRET"] = creds["DCI_API_SECRET"]
    loader = DataLoader()
    vault_secrets = CLI.setup_vault_secrets(
        loader=loader, vault_ids=[get_vault_client()]
    )
    ansible_yaml = []
    for assoc in from_yaml(data, vault_secrets=vault_secrets):
        assoc["_pipeline_path_"] = path
        ansible_yaml.append(assoc)
    return ansible_yaml


def load_credentials(stage, config_dir):
    cred_path = stage.get(
        "dci_credentials",
        "%s/%s/dci_credentials.yml"
        % (config_dir, os.path.dirname(stage["ansible_playbook"])),
    )

    if cred_path[0] != "/":
        cred_path = "%s/%s" % (config_dir, cred_path)

    log.info("Loading credentials from %s" % cred_path)
    with open(cred_path) as stream:
        dci_credentials = yaml.load(stream, Loader=yaml.SafeLoader)

    if "DCI_CS_URL" not in dci_credentials:
        dci_credentials["DCI_CS_URL"] = "https://api.distributed-ci.io/"

    return dci_credentials


def load_pipeline_user_credentials(pipeline_user_path):
    pipeline_user_abs_path = os.path.abspath(pipeline_user_path)
    if not os.path.exists(pipeline_user_abs_path):
        log.error("unable to find pipeline user file at %s" % pipeline_user_abs_path)
        sys.exit(1)
    with open(pipeline_user_abs_path) as stream:
        dci_credentials = yaml.load(stream, Loader=yaml.SafeLoader)
    if "DCI_CS_URL" not in dci_credentials:
        dci_credentials["DCI_CS_URL"] = "https://api.distributed-ci.io/"
    return dci_credentials


def generate_ansible_cfg(dci_ansible_dir, config_dir):
    fname = os.path.join(config_dir, "ansible.cfg")
    log.info("Generating %s using dci_ansible_dir=%s" % (fname, dci_ansible_dir))
    with open(fname, "w") as f:
        f.write(
            """[defaults]
library            = {dci_ansible_dir}/modules/
module_utils       = {dci_ansible_dir}/module_utils/
action_plugins     = {dci_ansible_dir}/action_plugins/
callback_plugins   = {dci_ansible_dir}/callback/
filter_plugins     = {dci_ansible_dir}/filter_plugins/
callback_whitelist = dci
log_path           = ansible.log
""".format(
                dci_ansible_dir=dci_ansible_dir
            )
        )


def get_types_of_stage(pipeline):
    names = []
    for stage in pipeline:
        if stage["type"] not in names:
            names.append(stage["type"])
    return names


def get_stages(names, pipeline):
    stages = []
    if names:
        # manage cases where a single entry is provided
        if not is_list(names):
            names = [names]
        for stage in pipeline:
            for name in names:
                if stage["name"] == name or stage["type"] == name:
                    stages.append(stage)
    return stages


def get_prev_stages(stage, pipeline):
    stages = get_stages(stage.get("prev_stages"), pipeline)
    try:
        idx = stages.index(stage)
        stages = stages[:idx]
    except ValueError:
        pass
    stages.reverse()
    return stages


def build_remoteci_context(dci_credentials):
    return dci_context.build_signature_context(
        dci_client_id=dci_credentials["DCI_CLIENT_ID"],
        dci_api_secret=dci_credentials["DCI_API_SECRET"],
        dci_cs_url=dci_credentials["DCI_CS_URL"],
    )


def build_pipeline_user_context(dci_credentials):
    return dci_context.build_dci_context(
        dci_login=dci_credentials["DCI_PIPELINE_USERNAME"],
        dci_password=dci_credentials["DCI_PIPELINE_PASSWORD"],
        dci_cs_url=dci_credentials["DCI_CS_URL"],
    )


def is_stage_with_fixed_components(stage):
    for component_type in stage["components"]:
        if "=" in component_type:
            return True
    return False


def get_components(context, stage, topic_id, tag=None):
    components = []
    if "components" not in stage:
        stage["components"] = []
    for component_type in stage["components"]:
        c_type = component_type
        c_name = ""
        where_query = "type:%s%s" % (c_type, (",tags:%s" % tag) if tag else "")
        if "?" in c_type:
            c_type, c_query = c_type.split("?", 1)
            where_query = "type:%s,%s" % (c_type, ",".join(c_query.split("&")))
        elif "=" in c_type:
            c_type, c_name = c_type.split("=", 1)
            where_query = "type:%s,name:%s" % (c_type, c_name)
        where_query = (
            where_query.replace("%3a", ":").replace("%3f", "?").replace("%26", "&")
        )
        resp = dci_topic.list_components(
            context, topic_id, limit=1, offset=0, sort="-released_at", where=where_query
        )
        if resp.status_code == 200:
            log.info("Got component %s[%s]: %s" % (c_type, c_name, resp.text))
            if resp.json()["_meta"]["count"] > 0:
                components.append(resp.json()["components"][0])
            else:
                log.error(
                    "No %s[%s] component, topic_id %s" % (c_type, c_name, topic_id)
                )
        else:
            log.error(
                "Unable to fetch component %s/%s for topic %s: %s"
                % (c_type, c_name, stage["topic"], resp.text)
            )
    return components, stage


def get_topic_id(context, stage):
    topic_res = dci_topic.list(context, where="name:" + stage["topic"])
    if topic_res.status_code == 200:
        topics = topic_res.json()["topics"]
        log.debug("topics: %s" % topics)
        if len(topics) == 0:
            log.error("topic %s not found" % stage["topic"])
            return None
        return topics[0]["id"]
    else:
        log.error("Unable to get topic %s: %s" % (stage["topic"], topic_res.text))
    return None


def get_data_dir(job_info, stage):
    for base_dir in (
        os.getenv("DCI_PIPELINE_DATADIR"),
        "/var/lib/dci-pipeline",
        "/tmp/dci-pipeline",
    ):
        try:
            if base_dir:
                d = os.path.join(base_dir, stage["name"], job_info["job"]["id"])
                os.makedirs(d, mode=0o700)
                with open(os.path.join(d, "job_info.yaml"), "w") as f:
                    yaml.dump(job_info, f, Dumper=AnsibleDumper)
                with open(os.path.join(d, "stage.yaml"), "w") as f:
                    yaml.dump(stage, f, Dumper=AnsibleDumper)
                job_info["data_dir"] = d
                break
        except PermissionError:
            log.info("No permission to write in %s" % base_dir)
            continue
        except Exception:
            log.exception(base_dir)
            continue
    else:
        log.error("Unable to find a suitable data_dir")
        sys.exit(4)
    return d


def schedule_job(
    stage,
    remoteci_context,
    pipeline_user_context,
    tag=None,
    prev_components=None,
    previous_job_id=None,
    pipeline_id=None,
):
    log.info(
        "scheduling job %s on topic %s%s previous_job_id=%s pipeline_id=%s"
        % (
            stage["name"],
            stage["topic"],
            " with tag %s" % tag if tag else "",
            previous_job_id,
            pipeline_id,
        )
    )

    topic_id = get_topic_id(remoteci_context, stage)
    if not topic_id:
        return None
    user_context = remoteci_context
    if pipeline_user_context:
        user_context = pipeline_user_context
    components, stage = get_components(user_context, stage, topic_id, tag)

    if len(stage["components"]) != len(components):
        log.error(
            "Unable to get all components %d out of %d"
            % (len(components), len(stage["components"]))
        )
        return None

    if prev_components:
        prev_comp_names = [c["name"] for c in prev_components]
        for comp in components:
            if comp["name"] not in prev_comp_names:
                log.info(
                    "Found a different component to retry %s from %s"
                    % (comp["name"], prev_comp_names)
                )
                break
        else:
            log.info(
                "No different components with tag %s. Not restarting the job." % tag
            )
            return None

    pipeline_data = dict(stage)
    if "job_info" in pipeline_data:
        del pipeline_data["job_info"]
    if (
        "ansible_extravars" in pipeline_data
        and "job_info" in pipeline_data["ansible_extravars"]
    ):
        del pipeline_data["ansible_extravars"]["job_info"]

    schedule = dci_job.create(
        remoteci_context,
        topic_id=topic_id,
        comment=stage.get("comment"),
        name=stage.get("name"),
        configuration=stage.get("configuration"),
        url=stage.get("url"),
        components=[c["id"] for c in components],
        data={"pipeline": clean_ansible_objects(pipeline_data)},
        previous_job_id=previous_job_id,
        pipeline_id=pipeline_id,
    )
    if schedule.status_code == 201:
        scheduled_job_id = schedule.json()["job"]["id"]
        scheduled_job = dci_job.get(
            remoteci_context, scheduled_job_id, embed="topic,remoteci,components"
        )
        if scheduled_job.status_code == 200:
            job_id = scheduled_job.json()["job"]["id"]
            dci_jobstate.create(
                remoteci_context, status="new", comment="job scheduled", job_id=job_id
            )
            for c in scheduled_job.json()["job"]["components"]:
                if c["id"] not in [c["id"] for c in components]:
                    log.error(
                        "%s is not a scheduled components from %s"
                        % (c["name"], [comp["name"] for comp in components])
                    )
                    return None
            job_info = scheduled_job.json()
            get_data_dir(job_info, stage)

            log.info("Scheduled DCI job %s" % job_id)

            return job_info
        else:
            log.error("error getting schedule info: %s" % scheduled_job.text)
    else:
        log.error("error scheduling: %s" % schedule.text)
    return None


def add_tags_to_job(job_id, tags, context):
    for tag in tags:
        log.info("Setting tag %s on job %s" % (tag, job_id))
        dci_job.add_tag(context, job_id, tag)


def add_tag_to_component(component_id, tag, context):
    log.info("Setting tag %s on component %s" % (tag, component_id))
    dci_component.add_tag(context, component_id, tag)


def get_list(stage, key):
    val = stage.get(key)
    if val and isinstance(val, str):
        val = [val]
    return val


def get_vault_client():
    return os.getenv("DCI_VAULT_CLIENT", shutil.which("dci-vault-client"))


def build_cmdline(stage):
    cmd = "--vault-id %s" % get_vault_client()
    for key, switch in (
        ("ansible_tags", "--tags"),
        ("ansible_skip_tags", "--skip-tags"),
    ):
        lst = get_list(stage, key)

        if lst:
            cmd += " " + switch + " " + ",".join(lst)

    if "ansible_extravars" in stage:
        cmd += " -e '%s'" % json.dumps(
            stage["ansible_extravars"], cls=AnsibleJSONEncoder
        )

    if "ansible_extravars_files" in stage:
        for extra_file in stage["ansible_extravars_files"]:
            if extra_file[0] != "/":
                extra_file = os.path.join(
                    os.path.abspath(os.path.dirname(stage["_pipeline_path_"])),
                    extra_file,
                )
            cmd += f" -e '@{extra_file}'"

    log.info('cmdline="%s"' % cmd)

    return cmd


def check_stats(stats):
    if (
        stats.get("ok", {}) == {}
        and stats.get("changed", {}) == {}
        and stats.get("processed", {}) == {}
    ):
        log.error("Nothing has been executed")
        return False
    return True


def stage_check_path(stage, key, data_dir):
    path = stage.get(key)
    if path:
        if path[0] != "/":
            path = os.path.join(data_dir, path)
            if not os.path.exists(path):
                log.error("No %s file: %s." % (key, path))
                raise FileNotFoundError(path)
    return path


def find_dci_ansible_dir(stage):
    for dci_ansible_dir in (
        os.getenv("DCI_ANSIBLE_DIR"),
        stage.get("dci_ansible_dir"),
        os.path.join(os.path.dirname(TOPDIR), "dci-ansible"),
        "/usr/share/dci",
    ):
        if dci_ansible_dir and os.path.isfile(
            os.path.join(dci_ansible_dir, "callback", "dci.py")
        ):
            log.info("Found dci.py in %s" % os.path.join(dci_ansible_dir, "callback"))
            envvars = {
                "ANSIBLE_CALLBACK_PLUGINS": os.path.join(dci_ansible_dir, "callback"),
            }
            if stage.get("ansible_envvars"):
                if not isinstance(stage.get("ansible_envvars"), dict):
                    log.error("The 'ansible_envvars' stage key is not a dict.")
                    sys.exit(1)
                envvars.update(stage.get("ansible_envvars"))
            return dci_ansible_dir, envvars
    else:
        log.warning(
            "Unable to find dci.py callback. Reverting to default: %s."
            % dci_ansible_dir
        )
        return dci_ansible_dir, {}


def upload_ansible_log(context, ansible_log_dir, stage):
    ansible_log = os.path.join(ansible_log_dir, "ansible.log")
    if os.path.exists(ansible_log):
        log.info("Uploading ansible.log from %s" % ansible_log)
        dci_file.create(
            context,
            "ansible.log",
            file_path=ansible_log,
            job_id=stage["job_info"]["job"]["id"],
        )
    else:
        log.error("ansible.log not found in %s" % ansible_log)


def update_job_info(context, stage):
    resp = dci_job.get(context, stage["job_info"]["job"]["id"])
    if resp.status_code != 200:
        log.error("Unable to get job info: %s" % resp.text())
    else:
        stage["job_info"].update(resp.json())


def run_stage(context, stage, dci_credentials, data_dir, cancel_cb):
    stage = dict(stage)
    stage_metas, stage = pre_process_stage(stage)
    job_info = stage["job_info"]
    private_data_dir = job_info["data_dir"]
    inventory = stage_check_path(stage, "ansible_inventory", data_dir)
    dci_ansible_dir, envvars = find_dci_ansible_dir(stage)
    ansible_cfg = stage_check_path(stage, "ansible_cfg", data_dir)
    if ansible_cfg:
        shutil.copy(ansible_cfg, os.path.join(private_data_dir, "ansible.cfg"))
    else:
        generate_ansible_cfg(dci_ansible_dir, private_data_dir)
    log.info(
        "running stage: %s%s private_data_dir=%s"
        % (
            stage["name"],
            " with inventory %s" % inventory if inventory else "",
            private_data_dir,
        )
    )
    envvars.update(dci_credentials)
    run = ansible_runner.run(
        private_data_dir=private_data_dir,
        playbook=os.path.join(data_dir, stage["ansible_playbook"]),
        verbosity=VERBOSE_LEVEL,
        envvars=envvars,
        # Variables are passed on the cmdline to allow vault encrypted
        # vars to work
        cmdline=build_cmdline(stage),
        extravars={"job_info": job_info},
        inventory=inventory,
        quiet=False,
        cancel_callback=cancel_cb,
    )
    stage["job_info"]["stats"] = run.stats
    stage["job_info"]["rc"] = run.rc
    log.info("stats=%s" % run.stats)
    upload_ansible_log(context, private_data_dir, stage)
    post_process_stage(context, stage, stage_metas)
    update_job_info(context, stage)
    return run.rc == 0 and run.stats and check_stats(run.stats) and not cancel_cb()


def usage(ret, cmd):
    print("Usage: %s [<stage name>:<key>=<value>...] [<pipeline file>]" % cmd)
    sys.exit(ret)


def process_args(args):
    """process command line arguments

    return file names and overload parameters as a dict
    from <stage name>:<key>=<value> arguments"""
    cmd = args[0]
    args = args[1:]
    ret = []
    lst = []
    opt = {"name": "pipeline"}
    while True:
        if len(args) == 0:
            break
        arg = args.pop(0)
        if arg == "-h" or arg == "--help":
            usage(0, cmd)
        # Process args with a : in them and let other args be pipeline
        # filenames.
        if ":" not in arg:
            ret.append(arg)
            continue
        # Allow these syntaxes to overload stage settings:
        # <name>:<key>=<value> value can be a list separated by ','
        # <name>:<key>=<subkey>:<value> to return a dict
        try:
            overload = {}
            name, rest = arg.split(":", 1)
            key, value = rest.split("=", 1)
            if ":" in value and value[:7] != "http://" and value[:8] != "https://":
                res = {}
                k, v = value.split(":", 1)
                if "," in v:
                    res[k] = v.split(",")
                    if res[k][-1] == "":
                        res[k] = res[k][:-1]
                else:
                    res[k] = v
                value = res
            elif "," in value:
                value = value.split(",")
                if value[-1] == "":
                    value = value[:-1]
            dct = overload.get(name, {})
            dct[key] = value
            overload[name] = dct
            # @pipeline is a special name to set options for the whole pipeline
            if name == "@pipeline":
                opt.update(overload["@pipeline"])
            else:
                if name[0] == "@":
                    raise ValueError(f"Invalid name {name}")
                lst.append(overload)
        except ValueError:
            log.error('Invalid syntax: "%s"' % arg)
            usage(3, cmd)
    return lst, ret, opt


def is_list(elt):
    return isinstance(elt, list)


def is_dict(elt):
    return isinstance(elt, dict)


def is_string(elt):
    return isinstance(elt, str)


def overload_dicts(overload, target):
    """do a complex dict update

    overload_dicts({'components': ['ocp=12', 'cnf-tests'],
                    'ansible_extravars': {'dci_comment': 'universal answer'},
                   {'components': ['ocp', 'ose-tests'],
                    'ansible_extravars': {'answer': 42}})
    => {'components': ['ocp=12', 'cnf-tests', 'ose-tests'],
        'ansible_extravars': {'answer': 42', dci_comment': 'universal answer'}}"""
    # special case for components with a single entry
    if "components" in overload and is_string(overload["components"]):
        overload["components"] = [overload["components"]]
    for key in overload:
        if key not in target:
            target[key] = overload[key]
        else:
            if is_list(overload[key]) and is_list(target[key]):
                to_add = []
                for elt in overload[key]:
                    eq_key = elt.replace("?", "=", 1).split("=", 1)[0]
                    for loop in range(len(target[key])):
                        if (
                            target[key][loop].replace("?", "=", 1).split("=", 1)[0]
                            == eq_key
                        ):
                            target[key][loop] = elt
                            break
                    else:
                        to_add.append(elt)
                target[key] = target[key] + to_add
            elif is_dict(overload[key]) and is_dict(target[key]):
                target[key].update(overload[key])
            else:
                target[key] = overload[key]
    return target


def get_config(args):
    lst, args, opts = process_args(args)
    log.info(f"overload={lst} options={opts}")
    if len(args) == 0:
        args = [os.path.join(TOPDIR, "dcipipeline/pipeline.yml")]
    pipeline = []
    for config in args:
        config_dir = os.path.abspath(os.path.dirname(config))
        stages = load_stage_file(config, config_dir)
        pipeline += stages
    # When 2 consecutive stages have the same name, do a
    # special merge
    for idx in range(len(pipeline) - 1, 0, -1):
        if pipeline[idx - 1]["name"] == pipeline[idx]["name"]:
            # Do a copy of the keys to avoid a runtime error when
            # we delete keys
            for key in list(pipeline[idx].keys()):
                # Special merge: concat lists and merge dicts
                if (
                    key in pipeline[idx]
                    and key in pipeline[idx - 1]
                    and type(pipeline[idx][key]) == type(pipeline[idx - 1][key])  # noqa
                ):
                    if isinstance(pipeline[idx][key], list):
                        pipeline[idx - 1][key] += pipeline[idx][key]
                        del pipeline[idx][key]
                    elif isinstance(pipeline[idx][key], dict):
                        pipeline[idx - 1][key].update(pipeline[idx][key])
                        del pipeline[idx][key]
            pipeline[idx - 1].update(pipeline[idx])
            del pipeline[idx]
    # Process global options from @pipeline
    for overload in lst:
        for name in overload:
            stage = get_stages(name, pipeline)
            if not stage:
                log.error("No such stage %s" % name)
                sys.exit(3)
            overload_dicts(overload[name], stage[0])
    return config_dir, pipeline, opts


def set_success_tag(stage, job_info, context):
    if "success_tag" in stage:
        for component in job_info["job"]["components"]:
            add_tag_to_component(component["id"], stage["success_tag"], context)


def lookup_stage_by_outputs(key, stages):
    for stage in stages:
        if "outputs" in stage and "job_info" in stage and key in stage["outputs"]:
            return stage
    return None


def create_inputs(config_dir, prev_stages, stage, job_info):
    if "inputs" not in stage:
        return

    top_dir = "%s/inputs" % job_info["data_dir"]
    try:
        os.makedirs(top_dir)
    except Exception:
        pass

    job_info["inputs"] = {}
    for key in stage["inputs"]:
        prev_stage = lookup_stage_by_outputs(key, prev_stages)
        if prev_stage:
            prev_stage_outputs_key = prev_stage["job_info"]["outputs"][key]
            stage_inputs_key = "%s/%s" % (
                top_dir,
                os.path.basename(prev_stage_outputs_key),
            )
            log.info("Copying %s into %s" % (prev_stage_outputs_key, stage_inputs_key))
            with open(stage_inputs_key, "wb") as ofile:
                with open(prev_stage_outputs_key, "rb") as ifile:
                    ofile.write(ifile.read())
            if "ansible_extravars" not in stage:
                stage["ansible_extravars"] = {}
            log.debug(
                "setting ansible var %s to %s"
                % (stage["inputs"][key], stage_inputs_key)
            )
            stage["ansible_extravars"][stage["inputs"][key]] = stage_inputs_key
        else:
            log.error(
                "Unable to find outputs for key %s in stages %s"
                % (key, ", ".join([s["name"] for s in prev_stages]))
            )


def add_outputs_paths(job_info, stage):

    if "outputs" not in stage:
        return

    outputs_job_directory_prefix = "%s/outputs" % job_info["data_dir"]
    os.makedirs(outputs_job_directory_prefix)
    outputs_keys_paths = {}
    for key in stage["outputs"]:
        outputs_keys_paths[key] = "%s/%s" % (
            outputs_job_directory_prefix,
            stage["outputs"][key],
        )
    job_info["outputs"] = outputs_keys_paths


def compute_tags(stage, prev_stages):
    tags = ["job:" + stage["name"], "job-type:" + stage["type"]]

    if "DCI_QUEUE_JOBID" in os.environ:
        tags.append("pipeline-id:%s" % os.environ["DCI_QUEUE_JOBID"])

    if "ansible_inventory" in stage:
        tags.append("inventory:" + os.path.basename(stage["ansible_inventory"]))

    for prev_stage in prev_stages:
        if prev_stage and "job_info" in prev_stage:
            log.info("prev stage: %s" % prev_stage)
            for component in prev_stage["job_info"]["job"]["components"]:
                tags.append(
                    "prev-component:%s:%s/%s"
                    % (component["type"], prev_stage["topic"], component["name"])
                )
            tags.append("prev-job:" + prev_stage["job_info"]["job"]["id"])
            break
    return tags


def set_job_to_final_state(context, job_id, killed_func):
    j = dci_job.get(context, job_id)
    if j.status_code != 200:
        log.error("Unable to get job %s, error: %s" % (job_id, j.text))
        return
    if j.json()["job"]["status"] not in _JOB_FINAL_STATUSES:
        j_states = dci_job.list_jobstates(context, job_id)
        if j_states.status_code != 200:
            log.error(
                "Unable to list jobstates of job %s, error: %s"
                % (job_id, j_states.text)
            )
            return
        if killed_func() and j_states.json()["jobstates"][0]["status"] != "killed":
            dci_jobstate.create(context, "killed", job_id=job_id, comment="killed")
        elif j_states.json()["jobstates"][0]["status"] in _JOB_PRODUCT_STATUSES:
            dci_jobstate.create(context, "failure", job_id=job_id, comment="failure")
        else:
            dci_jobstate.create(context, "error", job_id=job_id, comment="error")


def run_stages(
    stage_type,
    pipeline,
    config_dir,
    previous_job_id,
    previous_topic,
    cancel_cb,
    options,
):
    stages = get_stages(stage_type, pipeline)
    errors = 0
    for stage in stages:
        dci_credentials = load_credentials(stage, config_dir)
        dci_remoteci_context = build_remoteci_context(dci_credentials)

        dci_pipeline_user_context = None
        if "pipeline_user" in stage:
            dci_pipeline_user_credentials = load_pipeline_user_credentials(
                stage["pipeline_user"]
            )
            dci_pipeline_user_context = build_pipeline_user_context(
                dci_pipeline_user_credentials
            )

        if "pipeline_id" not in options:
            context = (
                dci_pipeline_user_context
                if dci_pipeline_user_context is not None
                else dci_remoteci_context
            )
            team_id = dci_identity.my_team_id(context)
            res = dci_pipeline.create(context, options["name"], team_id)
            if res.status_code == 201:
                options["pipeline_id"] = res.json()["pipeline"]["id"]

        if (
            "use_previous_topic" in stage
            and stage["use_previous_topic"] is True
            and previous_topic is not None
        ):
            log.info(
                "Setting topic to %s for %s from previous topic"
                % (previous_topic, stage["name"])
            )
            stage["topic"] = previous_topic

        stage["job_info"] = schedule_job(
            stage,
            dci_remoteci_context,
            dci_pipeline_user_context,
            previous_job_id=previous_job_id,
            pipeline_id=options["pipeline_id"],
        )

        if not stage["job_info"]:
            log.error("Unable to schedule job %s. Skipping" % stage["name"])
            errors += 1
            continue

        _job_id = stage["job_info"]["job"]["id"]
        prev_stages = get_prev_stages(stage, pipeline)
        create_inputs(config_dir, prev_stages, stage, stage["job_info"])
        add_outputs_paths(stage["job_info"], stage)

        tags = compute_tags(stage, prev_stages)
        add_tags_to_job(_job_id, tags, dci_remoteci_context)

        if run_stage(
            dci_remoteci_context, stage, dci_credentials, config_dir, cancel_cb
        ):
            set_success_tag(stage, stage["job_info"], dci_remoteci_context)
        else:
            log.error(
                "Unable to run successfully job %s (%s)"
                % (stage["name"], stage["job_info"]["job"]["id"])
            )
            if (
                "fallback_last_success" in stage
                and not is_stage_with_fixed_components(stage)
                and not cancel_cb()
            ):
                log.info("Retrying with tag %s" % stage["fallback_last_success"])
                stage["failed_job_info"] = stage["job_info"]
                stage["job_info"] = schedule_job(
                    stage,
                    dci_remoteci_context,
                    dci_pipeline_user_context,
                    stage["fallback_last_success"],
                    stage["job_info"]["job"]["components"],
                    previous_job_id=previous_job_id,
                    pipeline_id=options["pipeline_id"],
                )

                if not stage["job_info"]:
                    log.error(
                        "Unable to schedule job %s on tag %s."
                        % (stage["name"], stage["fallback_last_success"])
                    )
                    errors += 1
                else:
                    _job_id_2 = stage["job_info"]["job"]["id"]
                    tags.append("fallback")
                    add_tags_to_job(_job_id_2, tags, dci_remoteci_context)
                    create_inputs(config_dir, prev_stages, stage, stage["job_info"])
                    add_outputs_paths(stage["job_info"], stage)
                    if run_stage(
                        dci_remoteci_context,
                        stage,
                        dci_credentials,
                        config_dir,
                        cancel_cb,
                    ):
                        set_success_tag(stage, stage["job_info"], dci_remoteci_context)
                    else:
                        log.error(
                            "Unable to run successfully job %s on tag %s"
                            % (stage["name"], stage["fallback_last_success"])
                        )
                        errors += 1
                    set_job_to_final_state(dci_remoteci_context, _job_id_2, cancel_cb)
            else:
                errors += 1
        set_job_to_final_state(dci_remoteci_context, _job_id, cancel_cb)
    return errors, stages


PIPELINE = []


def main(args=sys.argv):
    global PIPELINE
    del PIPELINE[:]
    signal_handler = SignalHandler()
    config_dir, pipeline, options = get_config(args)
    PIPELINE += pipeline

    previous_job_id = None
    previous_topic = None
    for stage_type in get_types_of_stage(pipeline):
        job_in_errors, stages = run_stages(
            stage_type,
            pipeline,
            config_dir,
            previous_job_id,
            previous_topic,
            signal_handler.called,
            options,
        )
        if job_in_errors != 0:
            log.error(
                "%d job%s in error at stage %s"
                % (job_in_errors, "s" if job_in_errors > 1 else "", stage_type)
            )
            if signal_handler.called():
                return 128 + signal_handler.signum
            else:
                for stage in stages:
                    if "job_info" in stage and stage["job_info"] is not None:
                        job_info = stage["job_info"]
                    elif (
                        "failed_job_info" in stage
                        and stage["failed_job_info"] is not None
                    ):
                        job_info = stage["failed_job_info"]
                    else:
                        job_info = None
                        log.error("No job_info found for stage %s" % stage["name"])
                    if job_info and "jobstates" in job_info["job"]:
                        job_states = sorted(
                            job_info["job"]["jobstates"],
                            key=lambda x: x["created_at"],
                        )
                        log.info(
                            "Stage %s status=%s"
                            % (stage["name"], job_states[-1]["status"])
                        )
                        if job_states[-1]["status"] == "error":
                            return 2
                    else:
                        log.error("No job.jobstate found for stage %s" % stage["name"])
                return 1
        if len(stages) > 0:
            previous_job_id = stages[0]["job_info"]["job"]["id"]
            previous_topic = stages[0]["job_info"]["job"]["topic"]["name"]
    log.info("Successful end of pipeline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
