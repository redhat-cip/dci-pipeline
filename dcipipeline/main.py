# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2024 Red Hat, Inc
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

import datetime
import json
import logging
import os
import shutil
import signal
import sys
import tempfile
import time
from json.decoder import JSONDecodeError

import ansible_runner
import yaml
from ansible.cli import CLI
from ansible.parsing.ajson import AnsibleJSONEncoder
from ansible.parsing.dataloader import DataLoader
from ansible.parsing.utils.yaml import from_yaml
from ansible.parsing.yaml.dumper import AnsibleDumper
from ansible.parsing.yaml.objects import AnsibleSequence
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


class DciError(Exception):
    pass


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


def pre_process_jobdef(jobdef):
    metas = {}
    if "ansible_envvars" not in jobdef:
        jobdef["ansible_envvars"] = {}

    # create sane default env variables
    if "JUNIT_TEST_CASE_PREFIX" not in jobdef["ansible_envvars"]:
        jobdef["ansible_envvars"]["JUNIT_TEST_CASE_PREFIX"] = "test_"
    if "JUNIT_TASK_CLASS" not in jobdef["ansible_envvars"]:
        jobdef["ansible_envvars"]["JUNIT_TASK_CLASS"] = "yes"
    if "JUNIT_OUTPUT_DIR" not in jobdef["ansible_envvars"]:
        jobdef["ansible_envvars"]["JUNIT_OUTPUT_DIR"] = "/@tmpdir"

    for k, v in jobdef["ansible_envvars"].items():
        if v != "/@tmpdir":
            continue
        jobdef["ansible_envvars"][k] = tempfile.mkdtemp(prefix="dci-pipeline-tmpdir")
        log.info("Created %s for env var %s" % (jobdef["ansible_envvars"][k], k))
        if "tmpdirs" not in metas:
            metas["tmpdirs"] = [{"name": k, "path": jobdef["ansible_envvars"][k]}]
        else:
            metas["tmpdirs"].append({"name": k, "path": jobdef["ansible_envvars"][k]})
    return metas, jobdef


def post_process_jobdef(context, jobdef, metas):
    if "tmpdirs" not in metas:
        return

    for tmpdir in metas["tmpdirs"]:
        if tmpdir["name"] == "JUNIT_OUTPUT_DIR":
            upload_junit_files_from_dir(context, jobdef, tmpdir["path"])
        try:
            shutil.rmtree(tmpdir["path"])
        except OSError as e:
            log.warning("unable to delete %s: %s" % (tmpdir, str(e)))


def upload_junit_files_from_dir(context, jobdef, dir):
    for f in os.listdir(dir):
        _abs_file_path = os.path.join(dir, f)
        if os.path.isfile(_abs_file_path) and f.endswith(".xml"):
            log.info("Uploading junit file: %s" % _abs_file_path)
            dci(
                dci_file.create,
                context,
                f[:-4],  # remove .xml at the end
                file_path=_abs_file_path,
                mime="application/junit",
                job_id=jobdef["job_info"]["job"]["id"],
            )
        else:
            log.warning("%s is not a junit file" % _abs_file_path)


def clean_ansible_objects(data):
    return yaml.load(yaml.dump(data, Dumper=AnsibleDumper), Loader=yaml.BaseLoader)


def load_jobdef_file(path, config_dir):
    # Read the pipeline jobdefs in 2 passes to be able to load first
    # the credentials file to be able to decrypt !vault statements in
    # the second pass.
    with open(os.path.expanduser(path)) as stream:
        data = stream.read(-1)
    # First pass without decrypting !vault
    jobdefs_raw_data = yaml.load(data, Loader=yaml.BaseLoader)
    try:
        creds = load_credentials(jobdefs_raw_data[0], config_dir)
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


def load_credentials(jobdef, config_dir):
    cred_path = jobdef.get(
        "dci_credentials",
        "%s/%s/dci_credentials.yml"
        % (config_dir, os.path.dirname(jobdef["ansible_playbook"])),
    )

    if cred_path[0] not in ("/", "~"):
        cred_path = "%s/%s" % (config_dir, cred_path)

    log.info("Loading credentials from %s" % cred_path)
    with open(os.path.expanduser(cred_path)) as stream:
        dci_credentials = yaml.load(stream, Loader=yaml.SafeLoader)

    if "DCI_CS_URL" not in dci_credentials:
        dci_credentials["DCI_CS_URL"] = "https://api.distributed-ci.io/"

    return dci_credentials


def load_pipeline_user_credentials(pipeline_user_path):
    pipeline_user_abs_path = os.path.abspath(os.path.expanduser(pipeline_user_path))
    if not os.path.exists(pipeline_user_abs_path):
        log.error("unable to find pipeline user file at %s" % pipeline_user_abs_path)
        sys.exit(1)
    with open(pipeline_user_abs_path) as stream:
        dci_credentials = yaml.load(stream, Loader=yaml.SafeLoader)
    if "DCI_CS_URL" not in dci_credentials:
        dci_credentials["DCI_CS_URL"] = "https://api.distributed-ci.io/"
    return dci_credentials


def generate_ansible_cfg(dci_ansible_dir, config_dir):
    fname = os.path.join(os.path.expanduser(config_dir), "ansible.cfg")
    log.info("Generating %s using dci_ansible_dir=%s" % (fname, dci_ansible_dir))
    with open(fname, "w") as f:
        f.write(
            """[defaults]
library            = {dci_ansible_dir}/modules/
module_utils       = {dci_ansible_dir}/module_utils/
action_plugins     = {dci_ansible_dir}/action_plugins/
callback_plugins   = {dci_ansible_dir}/callback/
filter_plugins     = {dci_ansible_dir}/filter_plugins/
collections_paths  = {ansible_collections_paths}
callback_whitelist = dci
log_path           = ansible.log
""".format(
                dci_ansible_dir=dci_ansible_dir,
                ansible_collections_paths=os.path.expanduser(
                    os.getenv(
                        "ANSIBLE_COLLECTIONS_PATHS",
                        "~/.ansible/collections:/usr/share/ansible/collections",
                    )
                ),
            )
        )


def get_jobdef_stage(jobdef):
    return jobdef.get("stage", jobdef.get("type"))


def get_stages_of_jobdefs(pipeline):
    names = []
    for jobdef in pipeline:
        name = get_jobdef_stage(jobdef)
        if name not in names:
            names.append(name)
    return names


def get_jobdefs_by_stage_or_name(lookup, pipeline):
    jobdefs = []
    if lookup:
        # manage cases where a single entry is provided
        if not is_list(lookup):
            lookup = [lookup]
        for jobdef in pipeline:
            for name in lookup:
                if jobdef["name"] == name or get_jobdef_stage(jobdef) == name:
                    jobdefs.append(jobdef)
    return jobdefs


def get_prev_jobdefs(jobdef, pipeline):
    jobdefs = get_jobdefs_by_stage_or_name(jobdef.get("prev_stages"), pipeline)
    try:
        idx = jobdefs.index(jobdef)
        jobdefs = jobdefs[:idx]
    except ValueError:
        pass
    jobdefs.reverse()
    return jobdefs


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


def is_jobdef_with_fixed_components(jobdef):
    for component_type in jobdef["components"]:
        if "=" not in component_type:
            return False
    return True


def filter2(li, func):
    yes = []
    no = []
    for e in li:
        if func(e):
            yes.append(e)
        else:
            no.append(e)
    return yes, no


def extract_tags(fields):
    tags, others = filter2(fields, lambda x: x.startswith("tags:"))
    return [f[5:] for f in tags], others


def extract_build_tags(fields):
    build_tags = []
    other_tags = []
    for field in fields:
        y, n = filter2(field.split(","), lambda x: x in ORDERED_TAGS)
        build_tags += y
        other_tags += n
    return build_tags, other_tags


def filter_type_tags(fields, c_type):
    ret = []
    for field in fields:
        if "?" in field:
            tag_type, tag = field.split("?", 1)
            if tag_type == c_type:
                ret.append(tag)
        else:
            ret.append(field)
    return ret


ORDERED_TAGS = ["build:nightly", "build:dev", "build:candidate", "build:ga"]


def generate_tags_query_clause(op, tags, nested=""):
    if len(tags) > 0:
        if op:
            return (
                f",{op}(contains(tags,"
                + "),contains(tags,".join(tags)
                + (f"){nested})" if nested != "" else "))")
            )
        else:
            return (
                ",contains(tags,"
                + "),contains(tags,".join(tags)
                + (f"){nested}" if nested != "" else ")")
            )
    else:
        return nested


def generate_query_from_tags(fallback_tags, build_tags, c_type):
    extra_build_tags, tags = extract_build_tags(filter_type_tags(fallback_tags, c_type))
    build_tags += extra_build_tags
    if len(build_tags) > 0:
        idx = max([ORDERED_TAGS.index(tag) for tag in build_tags])
        build_tags = ORDERED_TAGS[idx:]
    return generate_tags_query_clause(
        None, tags, generate_tags_query_clause("or", build_tags)
    )


def generate_and_query_clause(fields):
    if len(fields) > 0:
        qc = []
        for f in fields:
            k, v = f.split(":", 1)
            op = "eq"
            if v.endswith("*"):
                v = v.replace("*", "%")
                op = "ilike"
            qc.append(op + "(" + k + "," + v + ")")
        if len(fields) > 1:
            return "," + ",".join(qc)
        else:
            return "," + qc[0]
    else:
        return ""


def generate_query(c_type, fallback_tags):
    c_type = c_type.replace("%3a", ":").replace("%3f", "?").replace("%26", "&")
    if "?" in c_type:
        c_type, c_query = c_type.split("?", 1)
        c_query_tags, c_query_fields = extract_tags(c_query.split("&"))
        c_query_build_tags, c_query_other_tags = extract_build_tags(
            c_query_tags + fallback_tags
        )
        # "type:%s,%s" % (c_type, ",".join(c_query_fields))
        query_clause = (
            f"and(eq(type,{c_type}){generate_and_query_clause(c_query_fields)}"
            + generate_query_from_tags(c_query_other_tags, c_query_build_tags, c_type)
            + ")"
        )
    else:
        if "=" in c_type:
            c_type, c_version = c_type.split("=", 1)
            prefix = f"and(eq(state,active),eq(type,{c_type}),eq(version,{c_version})"
        else:
            prefix = f"and(eq(state,active),eq(type,{c_type})"
        query_clause = (
            prefix + generate_query_from_tags(fallback_tags, [], c_type) + ")"
        )
    return query_clause


def _get_created_after_from_today(days_before):
    time_of_day = datetime.datetime.today()
    created_after = time_of_day - datetime.timedelta(days=days_before)
    return f"{created_after.year}-{created_after.month}-{created_after.day}T00:00:00.000000"


def _get_components_by_kw(**kwargs):
    resp = dci(dci_topic.list_components, **kwargs)
    if resp.status_code == 200:
        log.info(
            "Got components: %s"
            % (
                [
                    f"{c['name']}={c['version']}[{c['type']}]"
                    for c in resp.json()["components"]
                ],
            )
        )
        if not resp.json()["_meta"]["count"]:
            return None
        return resp.json()["components"]
    else:
        log.error("Unable to fetch component: %s" % resp.text)
    return None


def _get_components_by_age_and_tag(context, topic_id, cmp_type, max_age, tag):
    where = f"type:{cmp_type}"
    if tag:
        where += f",tags:{tag}"
    if max_age:
        created_after = _get_created_after_from_today(max_age)
        components = _get_components_by_kw(
            context=context,
            id=topic_id,
            sort="-created_at",
            where=where,
            created_after=created_after,
        )
    else:
        components = _get_components_by_kw(
            context=context, id=topic_id, sort="-created_at", where=where
        )
    return components


def get_components(context, jobdef, topic_id, fallback_tags):
    components = []
    if fallback_tags and type(fallback_tags) not in (list, AnsibleSequence):
        fallback_tags = [fallback_tags]
    if "components" not in jobdef:
        jobdef["components"] = []
    for c_type in jobdef["components"]:
        if isinstance(c_type, dict):
            if "type" not in c_type:
                log.error("missing 'type' key")
                sys.exit(1)
            cmp_type = c_type["type"]
            priority_tags = c_type.get("priority_tags", [])
            max_age = c_type.get("max_age", None)
            log.info(
                f"get_comp topic_id={topic_id} cmp_type={cmp_type} priority_tags={priority_tags} max_age={max_age}"
            )
            compts = None
            if not priority_tags:
                compts = _get_components_by_age_and_tag(
                    context, topic_id, cmp_type, max_age, None
                )
            for tag in priority_tags:
                compts = _get_components_by_age_and_tag(
                    context, topic_id, cmp_type, max_age, tag
                )
                if compts:
                    break
            comp = None
            if compts and len(compts) > 0:
                comp = compts[0]
        else:
            query_clause = generate_query(c_type, fallback_tags)
            comp = get_comp(context, topic_id, c_type, None, query=query_clause)
        if comp:
            components.append(comp)
    return components, jobdef


def get_comp(context, topic_id, c_type, where_clause, error=True, query=None):
    comp = None
    log.info(
        f"get_comp topic_id={topic_id} c_type={c_type} where_clause={where_clause} query={query}"
    )
    resp = dci(
        dci_topic.list_components,
        context,
        topic_id,
        limit=1,
        offset=0,
        sort="-released_at",
        where=where_clause,
        query=query,
    )
    if resp.status_code == 200:
        log.info(
            "Got comp query result: %s[%s]: %s"
            % (
                c_type,
                where_clause,
                [f"{c['type']}={c['version']}" for c in resp.json()["components"]],
            )
        )
        if resp.json()["_meta"]["count"] > 0:
            comp = resp.json()["components"][0]
        else:
            if error:
                log.error(
                    "No %s[%s] component, topic_id %s"
                    % (c_type, where_clause, topic_id)
                )
    else:
        log.error(
            "Unable to fetch component %s[%s]: %s" % (c_type, where_clause, resp.text)
        )
    return comp


def get_topic_id(context, jobdef):
    topic_res = dci(dci_topic.list, context, where="name:" + jobdef["topic"])
    if topic_res.status_code == 200:
        topics = topic_res.json()["topics"]
        log.debug("topics: %s" % topics)
        if len(topics) == 0:
            log.error("topic %s not found" % jobdef["topic"])
            return None
        return topics[0]["id"]
    else:
        log.error("Unable to get topic %s: %s" % (jobdef["topic"], topic_res.text))
    return None


def get_data_dir(job_info, jobdef):
    for base_dir in (
        os.getenv("DCI_PIPELINE_DATADIR"),
        "/var/lib/dci-pipeline",
        "/tmp/dci-pipeline",
    ):
        try:
            if base_dir:
                d = os.path.join(
                    os.path.expanduser(base_dir), jobdef["name"], job_info["job"]["id"]
                )
                os.makedirs(d, mode=0o700)
                with open(os.path.join(d, "job_info.yaml"), "w") as f:
                    yaml.dump(job_info, f, Dumper=AnsibleDumper)
                with open(os.path.join(d, "jobdef.yaml"), "w") as f:
                    yaml.dump(jobdef, f, Dumper=AnsibleDumper)
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
    jobdef,
    remoteci_context,
    pipeline_user_context,
    tags=[],
    prev_components=None,
    previous_job_id=None,
    pipeline_id=None,
):
    previous_job_id = previous_job_id or jobdef.get("previous_job_id")
    log.info(
        "scheduling job %s on topic %s%s previous_job_id=%s pipeline_id=%s"
        % (
            jobdef["name"],
            jobdef["topic"],
            " with tags %s" % tags if tags else "",
            previous_job_id,
            pipeline_id,
        )
    )

    topic_id = get_topic_id(remoteci_context, jobdef)
    if not topic_id:
        return None
    user_context = remoteci_context
    if pipeline_user_context:
        user_context = pipeline_user_context
    components, jobdef = get_components(user_context, jobdef, topic_id, tags)

    if len(jobdef["components"]) != len(components):
        log.error(
            f"Unable to get all components {len(components)} out of {len(jobdef['components'])}: {[c['name'] for c in components]}"
        )
        return None

    if prev_components:
        prev_comp_versions = [c["version"] for c in prev_components]
        for comp in components:
            if comp["version"] not in prev_comp_versions:
                log.info(
                    "Found a different component to retry %s from %s"
                    % (comp["version"], prev_comp_versions)
                )
                break
        else:
            log.info(
                "No different components with tags %s. Not restarting the job." % tags
            )
            return None

    pipeline_data = dict(jobdef)
    if "job_info" in pipeline_data:
        del pipeline_data["job_info"]
    if (
        "ansible_extravars" in pipeline_data
        and "job_info" in pipeline_data["ansible_extravars"]
    ):
        del pipeline_data["ansible_extravars"]["job_info"]

    schedule = dci(
        dci_job.create,
        remoteci_context,
        topic_id=topic_id,
        comment=jobdef.get("comment"),
        name=jobdef.get("name"),
        configuration=jobdef.get("configuration"),
        url=jobdef.get("url"),
        components=[c["id"] for c in components],
        data={"pipeline": clean_ansible_objects(pipeline_data)},
        previous_job_id=previous_job_id,
        pipeline_id=pipeline_id,
    )
    if schedule.status_code == 201:
        scheduled_job_id = schedule.json()["job"]["id"]
        scheduled_job = dci(
            dci_job.get,
            remoteci_context,
            scheduled_job_id,
            embed="topic,remoteci,components",
        )
        if scheduled_job.status_code == 200:
            job_id = scheduled_job.json()["job"]["id"]
            dci(
                dci_jobstate.create,
                remoteci_context,
                status="new",
                comment="job scheduled",
                job_id=job_id,
            )
            for c in scheduled_job.json()["job"]["components"]:
                if c["id"] not in [c["id"] for c in components]:
                    log.error(
                        "%s is not a scheduled components from %s"
                        % (c["name"], [comp["name"] for comp in components])
                    )
                    return None
            job_info = scheduled_job.json()
            get_data_dir(job_info, jobdef)

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
        dci(dci_job.add_tag, context, job_id, tag)


def add_tag_to_component(component, tag, context):
    log.info(
        f"Setting tag {tag} on component {component['id']} {component['type']}={component['version']}"
    )
    dci(dci_component.add_tag, context, component["id"], tag)


def get_list(jobdef, key):
    val = jobdef.get(key)
    if val and isinstance(val, str):
        val = [val]
    return val


def get_vault_client():
    return os.getenv("DCI_VAULT_CLIENT", shutil.which("dci-vault-client"))


def build_cmdline(jobdef):
    cmd = "--vault-id %s" % get_vault_client()
    for key, switch in (
        ("ansible_tags", "--tags"),
        ("ansible_skip_tags", "--skip-tags"),
    ):
        lst = get_list(jobdef, key)

        if lst:
            cmd += " " + switch + " " + ",".join(lst)

    if "ansible_extravars" in jobdef:
        cmd += " -e '%s'" % json.dumps(
            jobdef["ansible_extravars"], cls=AnsibleJSONEncoder, separators=(",", ":")
        )

    if "ansible_extravars_files" in jobdef:
        for extra_file in jobdef["ansible_extravars_files"]:
            if extra_file[0] not in ("/", "~"):
                extra_file = os.path.join(
                    os.path.abspath(os.path.dirname(jobdef["_pipeline_path_"])),
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


def jobdef_check_path(jobdef, key, data_dir):
    path = jobdef.get(key)
    if path:
        if path[0] == "~":
            path = os.path.expanduser(path)
        if path[0] != "/":
            path = os.path.join(data_dir, path)
            if not os.path.exists(path):
                log.error("No %s file: %s." % (key, path))
                raise FileNotFoundError(path)
    return path


def find_dci_ansible_dir(jobdef):
    for dci_ansible_dir in (
        os.getenv("DCI_ANSIBLE_DIR"),
        jobdef.get("dci_ansible_dir"),
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
            if jobdef.get("ansible_envvars"):
                if not isinstance(jobdef.get("ansible_envvars"), dict):
                    log.error("The 'ansible_envvars' jobdef key is not a dict.")
                    sys.exit(1)
                envvars.update(jobdef.get("ansible_envvars"))
            return dci_ansible_dir, envvars
    else:
        log.warning(
            "Unable to find dci.py callback. Reverting to default: %s."
            % dci_ansible_dir
        )
        return dci_ansible_dir, {}


def upload_ansible_log(context, ansible_log_dir, jobdef):
    ansible_log = os.path.join(ansible_log_dir, "ansible.log")
    if os.path.exists(ansible_log):
        log.info("Uploading ansible.log from %s" % ansible_log)
        dci(
            dci_file.create,
            context,
            "ansible.log",
            file_path=ansible_log,
            job_id=jobdef["job_info"]["job"]["id"],
        )
    else:
        log.error("ansible.log not found in %s" % ansible_log)


def update_job_info(context, jobdef):
    resp = dci(dci_job.get, context, jobdef["job_info"]["job"]["id"])
    if resp.status_code != 200:
        log.error("Unable to get job info: %s" % resp)
        raise DciError("Unable to get job info: %s" % resp)
    else:
        jobdef["job_info"].update(resp.json())


def run_jobdef(context, jobdef, dci_credentials, data_dir, cancel_cb):
    jobdef = dict(jobdef)
    jobdef_metas, jobdef = pre_process_jobdef(jobdef)
    job_info = jobdef["job_info"]
    private_data_dir = job_info["data_dir"]
    inventory = jobdef_check_path(jobdef, "ansible_inventory", data_dir)
    dci_ansible_dir, envvars = find_dci_ansible_dir(jobdef)
    ansible_cfg = jobdef_check_path(jobdef, "ansible_cfg", data_dir)
    if ansible_cfg:
        shutil.copy(ansible_cfg, os.path.join(private_data_dir, "ansible.cfg"))
    else:
        generate_ansible_cfg(dci_ansible_dir, private_data_dir)
    # force the use of the ansible.cfg we just created
    os.environ["ANSIBLE_CONFIG"] = os.path.join(private_data_dir, "ansible.cfg")
    envvars["ANSIBLE_CONFIG"] = os.environ["ANSIBLE_CONFIG"]
    log.info(
        "running jobdef: %s%s private_data_dir=%s env=%s"
        % (
            jobdef["name"],
            " with inventory %s" % inventory if inventory else "",
            private_data_dir,
            envvars,
        )
    )
    envvars.update(dci_credentials)
    envvars["DCI_JOB_ID"] = job_info["job"]["id"]
    # Export the default vault id to be able to decrypt vault
    # encrypted vars in sub-processes
    envvars["ANSIBLE_VAULT_IDENTITY_LIST"] = get_vault_client()
    # export DCI_PLAYBOOK_ARGS to be able to call sub ansible-playbook
    # cmd with the same arguments
    cmdline = build_cmdline(jobdef)
    envvars["DCI_PLAYBOOK_ARGS"] = cmdline
    if "inventory_playbook" in jobdef:
        log.info("Running inventory playbook %s" % jobdef["inventory_playbook"])
        run = ansible_runner.run(
            private_data_dir=private_data_dir,
            playbook=os.path.join(data_dir, jobdef["inventory_playbook"]),
            verbosity=VERBOSE_LEVEL,
            envvars=envvars,
            # Variables are passed on the cmdline to allow vault encrypted
            # vars to work
            cmdline=cmdline,
            extravars={"job_info": job_info, "ansible_inventory": inventory},
            quiet=False,
            cancel_callback=cancel_cb,
        )
        if run.rc != 0 or cancel_cb():
            log.error("Inventory playbook failed: %s or canceled" % run.rc)
            return False

    playbook_path = os.path.join(data_dir, jobdef["ansible_playbook"])
    log.info("Launching playbook %s in %s" % (playbook_path, private_data_dir))
    run = ansible_runner.run(
        private_data_dir=private_data_dir,
        playbook=playbook_path,
        verbosity=VERBOSE_LEVEL,
        envvars=envvars,
        # Variables are passed on the cmdline to allow vault encrypted
        # vars to work
        cmdline=build_cmdline(jobdef),
        extravars={"job_info": job_info},
        inventory=inventory,
        quiet=False,
        cancel_callback=cancel_cb,
    )
    jobdef["job_info"]["stats"] = run.stats
    jobdef["job_info"]["rc"] = run.rc
    log.info("stats=%s" % run.stats)
    upload_ansible_log(context, private_data_dir, jobdef)
    post_process_jobdef(context, jobdef, jobdef_metas)
    update_job_info(context, jobdef)
    log.info("Result rc=%d stats=%s " % (run.rc, run.stats))
    return run.rc == 0 and run.stats and check_stats(run.stats) and not cancel_cb()


def usage(ret, cmd):
    print("Usage: %s [<jobdef name>:<key>=<value>...] [<pipeline file>]" % cmd)
    sys.exit(ret)


def process_args(args):
    """process command line arguments

    return file names and overload parameters as a dict
    from <jobdef name>:<key>=<value> arguments"""
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
        # Allow these syntaxes to overload jobdef settings:
        # <name>:<key>=<value> value can be a list separated by ','
        # <name>:<key>=<subkey>:<value> to return a dict
        # <name>:<key>={"subkey1":"value1","subkey2":"value2",...},
        #     a json object returned as a dict
        try:
            overload = {}
            name, rest = arg.split(":", 1)
            key, value = rest.split("=", 1)
            try:
                value = json.loads(value)
            except JSONDecodeError:
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
                if len(name) == 0:
                    raise ValueError(f"No name {arg}")
                elif name[0] == "@":
                    raise ValueError(f"Invalid name {arg}")
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
                        if isinstance(target[key][loop], dict):
                            if eq_key == target[key][loop]["type"]:
                                target[key][loop] = elt
                                break
                        elif (
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
        jobdefs = load_jobdef_file(config, config_dir)
        pipeline += jobdefs
    # When 2 consecutive jobdefs have the same name, do a
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
            jobdef = get_jobdefs_by_stage_or_name(name, pipeline)
            if not jobdef:
                log.error("No such jobdef %s" % name)
                sys.exit(3)
            overload_dicts(overload[name], jobdef[0])
    return config_dir, pipeline, opts


def set_success_tag(jobdef, job_info, context):
    if "success_tag" in jobdef:
        for component in job_info["job"]["components"]:
            add_tag_to_component(component, jobdef["success_tag"], context)


def lookup_jobdef_by_outputs(key, jobdefs):
    for jobdef in jobdefs:
        if "outputs" in jobdef and "job_info" in jobdef and key in jobdef["outputs"]:
            return jobdef
    return None


def create_inputs(config_dir, prev_jobdefs, jobdef, job_info):
    if "inputs" not in jobdef:
        return

    top_dir = os.path.expanduser("%s/inputs" % job_info["data_dir"])
    try:
        os.makedirs(top_dir)
    except Exception:
        pass

    job_info["inputs"] = {}
    for key in jobdef["inputs"]:
        prev_jobdef = lookup_jobdef_by_outputs(key, prev_jobdefs)
        if prev_jobdef:
            prev_jobdef_outputs_key = prev_jobdef["job_info"]["outputs"][key]
            jobdef_inputs_key = "%s/%s" % (
                top_dir,
                os.path.basename(prev_jobdef_outputs_key),
            )
            log.info(
                "Copying %s into %s" % (prev_jobdef_outputs_key, jobdef_inputs_key)
            )
            with open(jobdef_inputs_key, "wb") as ofile:
                with open(prev_jobdef_outputs_key, "rb") as ifile:
                    ofile.write(ifile.read())
            if "ansible_extravars" not in jobdef:
                jobdef["ansible_extravars"] = {}
            log.debug(
                "setting ansible var %s to %s"
                % (jobdef["inputs"][key], jobdef_inputs_key)
            )
            jobdef["ansible_extravars"][jobdef["inputs"][key]] = jobdef_inputs_key
        else:
            log.error(
                "Unable to find outputs for key %s in jobdefs %s"
                % (key, ", ".join([s["name"] for s in prev_jobdefs]))
            )


def add_outputs_paths(job_info, jobdef):
    if "outputs" not in jobdef:
        return

    outputs_job_directory_prefix = "%s/outputs" % job_info["data_dir"]
    os.makedirs(outputs_job_directory_prefix)
    outputs_keys_paths = {}
    for key in jobdef["outputs"]:
        outputs_keys_paths[key] = "%s/%s" % (
            outputs_job_directory_prefix,
            jobdef["outputs"][key],
        )
    job_info["outputs"] = outputs_keys_paths


def compute_tags(jobdef, prev_jobdefs):
    tags = ["stage:" + get_jobdef_stage(jobdef)]

    if "DCI_QUEUE_JOBID" in os.environ:
        tags.append("pipeline-id:%s" % os.environ["DCI_QUEUE_JOBID"])

    if "ansible_inventory" in jobdef:
        tags.append("inventory:" + os.path.basename(jobdef["ansible_inventory"]))

    return tags


def set_job_to_final_state(context, job_id, killed_func):
    j = dci(dci_job.get, context, job_id)
    if j.status_code != 200:
        log.error("Unable to get job %s, error: %s" % (job_id, j.text))
        return
    if j.json()["job"]["status"] not in _JOB_FINAL_STATUSES:
        j_states = dci(dci_job.list_jobstates, context, job_id)
        if j_states.status_code != 200:
            log.error(
                "Unable to list jobstates of job %s, error: %s"
                % (job_id, j_states.text)
            )
            return
        if killed_func() and j_states.json()["jobstates"][0]["status"] != "killed":
            dci(dci_jobstate.create, context, "killed", job_id=job_id, comment="killed")
        elif j_states.json()["jobstates"][0]["status"] in _JOB_PRODUCT_STATUSES:
            dci(
                dci_jobstate.create,
                context,
                "failure",
                job_id=job_id,
                comment="failure",
            )
        else:
            dci(dci_jobstate.create, context, "error", job_id=job_id, comment="error")


def run_stage(
    stage,
    pipeline,
    config_dir,
    cancel_cb,
    options,
):
    jobdefs = get_jobdefs_by_stage_or_name(stage, pipeline)
    errors = 0
    for jobdef in jobdefs:
        dci_credentials = load_credentials(jobdef, config_dir)
        dci_remoteci_context = build_remoteci_context(dci_credentials)

        prev_job_defs = get_jobdefs_by_stage_or_name(
            jobdef.get("prev_stages"), pipeline
        )
        prev_job_defs = [j for j in prev_job_defs if "job_info" in j]
        if len(prev_job_defs) > 0:
            previous_job_id = prev_job_defs[0]["job_info"]["job"]["id"]
            previous_topic = prev_job_defs[0]["job_info"]["job"]["topic"]["name"]
            log.info(
                "Setting previous job to % and previous topic to %s from job %s"
                % (previous_job_id, previous_topic, prev_job_defs[0]["name"])
            )
        else:
            log.info("No previous job for %s" % jobdef["name"])
            previous_job_id = None
            previous_topic = None

        dci_pipeline_user_context = None
        if "pipeline_user" in jobdef:
            dci_pipeline_user_credentials = load_pipeline_user_credentials(
                jobdef["pipeline_user"]
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
            res = dci(dci_pipeline.create, context, options["name"], team_id)
            if res.status_code == 201:
                options["pipeline_id"] = res.json()["pipeline"]["id"]

        if (
            "use_previous_topic" in jobdef
            and jobdef["use_previous_topic"] is True
            and previous_topic is not None
        ):
            log.info(
                "Setting topic to %s for %s from previous topic"
                % (previous_topic, jobdef["name"])
            )
            jobdef["topic"] = previous_topic

        jobdef["job_info"] = schedule_job(
            jobdef,
            dci_remoteci_context,
            dci_pipeline_user_context,
            previous_job_id=previous_job_id,
            pipeline_id=options["pipeline_id"],
        )

        if not jobdef["job_info"]:
            log.error("Unable to schedule job %s. Skipping" % jobdef["name"])
            errors += 1
            continue

        _job_id = jobdef["job_info"]["job"]["id"]
        prev_jobdefs = get_prev_jobdefs(jobdef, pipeline)
        create_inputs(config_dir, prev_jobdefs, jobdef, jobdef["job_info"])
        add_outputs_paths(jobdef["job_info"], jobdef)

        tags = compute_tags(jobdef, prev_jobdefs)
        add_tags_to_job(_job_id, tags, dci_remoteci_context)

        if run_jobdef(
            dci_remoteci_context, jobdef, dci_credentials, config_dir, cancel_cb
        ):
            set_success_tag(jobdef, jobdef["job_info"], dci_remoteci_context)
        else:
            log.error(
                "Unable to run successfully job %s (%s)"
                % (jobdef["name"], jobdef["job_info"]["job"]["id"])
            )
            if (
                "fallback_last_success" in jobdef
                and not is_jobdef_with_fixed_components(jobdef)
                and not cancel_cb()
            ):
                log.info("Retrying with tags %s" % jobdef["fallback_last_success"])
                jobdef["failed_job_info"] = jobdef["job_info"]
                jobdef["job_info"] = schedule_job(
                    jobdef,
                    dci_remoteci_context,
                    dci_pipeline_user_context,
                    jobdef["fallback_last_success"],
                    jobdef["job_info"]["job"]["components"],
                    previous_job_id=_job_id,
                    pipeline_id=options["pipeline_id"],
                )

                if not jobdef["job_info"]:
                    log.error(
                        "Unable to schedule job %s on tag %s."
                        % (jobdef["name"], jobdef["fallback_last_success"])
                    )
                    errors += 1
                else:
                    _job_id_2 = jobdef["job_info"]["job"]["id"]
                    tags.append("fallback")
                    add_tags_to_job(_job_id_2, tags, dci_remoteci_context)
                    create_inputs(config_dir, prev_jobdefs, jobdef, jobdef["job_info"])
                    add_outputs_paths(jobdef["job_info"], jobdef)
                    if run_jobdef(
                        dci_remoteci_context,
                        jobdef,
                        dci_credentials,
                        config_dir,
                        cancel_cb,
                    ):
                        set_success_tag(
                            jobdef, jobdef["job_info"], dci_remoteci_context
                        )
                    else:
                        log.error(
                            "Unable to run successfully job %s on tag %s"
                            % (jobdef["name"], jobdef["fallback_last_success"])
                        )
                        errors += 1
                    set_job_to_final_state(dci_remoteci_context, _job_id_2, cancel_cb)
            else:
                errors += 1
        set_job_to_final_state(dci_remoteci_context, _job_id, cancel_cb)
    return errors, jobdefs


PIPELINE = []


def main(args=sys.argv):
    global PIPELINE
    del PIPELINE[:]
    signal_handler = SignalHandler()
    config_dir, pipeline, options = get_config(args)
    PIPELINE += pipeline

    for stage in get_stages_of_jobdefs(pipeline):
        job_in_errors, jobdefs = run_stage(
            stage,
            pipeline,
            config_dir,
            signal_handler.called,
            options,
        )
        if job_in_errors != 0:
            log.error(
                "%d job%s in error at stage %s"
                % (job_in_errors, "s" if job_in_errors > 1 else "", stage)
            )
            if signal_handler.called():
                log.error(
                    "Signal %d received, stopping the pipeline" % signal_handler.signum
                )
                return 128 + signal_handler.signum
            else:
                log.info("Looking up last jobstates from %d jobdefs" % len(jobdefs))
                for jobdef in jobdefs:
                    if "job_info" in jobdef and jobdef["job_info"] is not None:
                        job_info = jobdef["job_info"]
                    elif (
                        "failed_job_info" in jobdef
                        and jobdef["failed_job_info"] is not None
                    ):
                        job_info = jobdef["failed_job_info"]
                    else:
                        job_info = None
                        log.error("No job_info found for jobdef %s" % jobdef["name"])
                    if job_info and "jobstates" in job_info["job"]:
                        job_states = sorted(
                            job_info["job"]["jobstates"],
                            key=lambda x: x["created_at"],
                        )
                        log.info(
                            "Jobdef %s status=%s"
                            % (jobdef["name"], job_states[-1]["status"])
                        )
                        if job_states[-1]["status"] == "error":
                            return 2
                    else:
                        log.error(
                            "No job.jobstate found for jobdef %s" % jobdef["name"]
                        )
                return 1
    log.info("Successful end of pipeline")
    return 0


_DEFAULT_WAIT = 30

_duration = _DEFAULT_WAIT


def dci(func, *args, **kwargs):
    "retry the DCI API call while there is an error 5xx"

    global _duration

    resp = func(*args, **kwargs)
    while resp.status_code // 100 == 5:
        log.error("DCI API error %s, retrying in %d seconds" % (resp, _duration))
        time.sleep(_duration)
        resp = func(*args, **kwargs)
        _duration *= 2
        # max duration at 10mn
        if _duration > 600:
            _duration = 600
    _duration = _DEFAULT_WAIT
    return resp


if __name__ == "__main__":
    sys.exit(main())
