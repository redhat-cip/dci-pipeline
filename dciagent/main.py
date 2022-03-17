# -*- coding: utf-8 -*-
#
# Copyright (C) 2021-2022 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""
"""

import atexit
import os
import shutil
import subprocess
import sys
import tempfile

import yaml
from ansible.cli import CLI
from ansible.parsing.dataloader import DataLoader
from ansible.parsing.utils.yaml import from_yaml
from ansible.parsing.yaml.dumper import AnsibleDumper

TOP_DIR = os.path.join(os.path.dirname(__file__))


def fix_path(filename, basedir):
    if filename[0] != "/":
        return os.path.abspath(os.path.join(basedir, filename))
    else:
        return filename


KEYS = [
    "ansible_inventory",
    "ansible_playbook",
    "dci_agent",
    "dci_credentials",
    "name",
    "type",
]

OPT_KEYS = [
    "ansible_cfg",
    "ansible_envvars",
    "ansible_skiptags",
    "ansible_tags",
    "comment",
    "components",
    "configuration",
    "dci_components_by_query",
    "fallback_last_success",
    "inputs",
    "outputs",
    "success_tag",
    "url",
    "topic",
]


def get_vault_client():
    return os.getenv("DCI_VAULT_CLIENT", shutil.which("dci-vault-client"))


def process_settings(settings_filename, pipelines, current_stage, prev_stage):
    loader = DataLoader()
    vault_secrets = CLI.setup_vault_secrets(
        loader=loader, vault_ids=[get_vault_client()]
    )
    with open(settings_filename) as stream:
        settings = from_yaml(stream, vault_secrets=vault_secrets)
    base_dir = os.path.dirname(settings_filename)
    # maintain keys used in settings below in KEYS (without the dci_ prefix)
    if "type" not in settings:
        settings["type"] = settings["dci_agent"]
    pipeline = {
        "name": settings["dci_name"]
        if "dci_name" in settings
        else settings["dci_agent"],
        "type": settings["type"],
        "ansible_playbook": fix_path(settings["ansible_playbook"], base_dir)
        if "ansible_playbook" in settings
        else "/usr/share/dci-{}-agent/dci-{}-agent.yml".format(
            settings["dci_agent"], settings["dci_agent"]
        ),
        "dci_credentials": fix_path(settings["dci_credentials"], base_dir)
        if "dci_credentials" in settings
        else os.path.join(os.path.dirname(settings_filename), "dci_credentials.yml"),
        "ansible_inventory": fix_path(settings["ansible_inventory"], base_dir)
        if "ansible_inventory" in settings
        else os.path.join(os.path.dirname(settings_filename), "hosts"),
    }
    # copy optional keys
    for key in OPT_KEYS:
        if key in settings:
            pipeline[key] = settings[key]
        if "dci_" + key in settings:
            pipeline[key] = settings["dci_" + key]
    # do a translation of the component queries
    if "components" not in settings and "dci_components_by_query" in settings:
        components_query = []
        for query in settings["dci_components_by_query"]:
            query_parts = []
            component_query = None
            for part in query.split(","):
                if part[:5] == "type:":
                    _, component_query = part.split(":", 1)
                else:
                    query_parts.append(part)
            if component_query is None:
                print(
                    "No type in dci_components_by_query entry: {}".format(query),
                    file=sys.stderr,
                )
                sys.exit(1)
            if len(query_parts) > 0:
                components_query.append(component_query + "?" + "&".join(query_parts))
            else:
                components_query.append(component_query)
        pipeline["components"] = components_query
    # cleanup dci-pipeline specific keys from settings
    for key in KEYS + OPT_KEYS:
        if key in settings:
            del settings[key]
        if "dci_" + key in settings:
            del settings["dci_" + key]
    pipeline["ansible_extravars"] = settings
    if current_stage is not None and current_stage != pipeline["type"]:
        prev_stage = current_stage if current_stage else pipeline["type"]
    current_stage = pipeline["type"]
    if prev_stage:
        pipeline["prev_stages"] = [prev_stage]
    pipelines.append(pipeline)

    return current_stage, prev_stage


def process_all_settings(args, first=None):
    pipelines = []
    dci_pipeline_args = [first] if first else []
    prev_stage = None
    current_stage = None
    # process args by replacing settings files by one pipeline file
    for arg in args:
        if arg[-12:] == "settings.yml":
            current_stage, prev_stage = process_settings(
                arg, pipelines, current_stage, prev_stage
            )
        else:
            dci_pipeline_args.append(arg)
    return dci_pipeline_args, pipelines


def process_args(args):
    tempdir = tempfile.mkdtemp()
    atexit.register(lambda: shutil.rmtree(tempdir))
    pipeline_filename = os.path.join(tempdir, "pipeline.yml")
    dci_pipeline_args, pipelines = process_all_settings(args, pipeline_filename)
    with open(pipeline_filename, "w") as pipeline_fd:
        yaml.dump(pipelines, pipeline_fd, Dumper=AnsibleDumper)
    return dci_pipeline_args


def main(args=sys.argv):
    pipeline_args = process_args(args[1:])
    dci_pipeline = os.path.join(TOP_DIR, "dci-pipeline")
    if not os.path.exists(dci_pipeline):
        dci_pipeline = "dci-pipeline"
    print("+", dci_pipeline, " ".join(pipeline_args), file=sys.stderr)
    ret = subprocess.run([dci_pipeline] + pipeline_args)
    return ret.returncode


def main_s2p(args=sys.argv):
    if len(args) < 3:
        print(
            "Usage: {} <settings file> (<settings file2>...) <pipeline file>".format(
                args[0]
            ),
            file=sys.stderr,
        )
        return 1
    _, pipelines = process_all_settings(args[1:-1])
    with open(args[2], "w") as pipeline_fd:
        yaml.dump(pipelines, pipeline_fd, Dumper=AnsibleDumper)
    return 0


if __name__ == "__main__":
    main()

# main.py ends here
