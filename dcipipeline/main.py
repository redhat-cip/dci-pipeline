# -*- coding: utf-8 -*-
#
# Copyright (C) Red Hat, Inc
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


import ansible_runner

import os
import sys
import yaml


def load_yaml_file(path):
    with open(path, 'r') as file:
        try:
            return yaml.load(file, Loader=yaml.SafeLoader)
        except yaml.YAMLError as exc:
            print(exc)
            sys.exit(1)


def check_pipeline(pipeline):
    def _check_agent_directory(path):
        print('check agent directory at %s' % path)
        pass


def get_ocp_stage(pipeline):
    for stage in pipeline:
        if stage['type'] == 'ocp':
            return dict(stage)
    return None


def get_cnf_stages(pipeline):
    cnf_stages = []
    for stage in pipeline:
        if stage['type'] == 'cnf':
            cnf_stages.append(dict(stage))
    return cnf_stages


def run_ocp(stage, dci_credentials, envvars):
    # schedule job on topic
    # run ocp playbook with job_info
    # return job_info
    print('running ocp stage: %s' % stage['name'])
    envvars = dict(envvars)
    envvars.update(dci_credentials)
    run = ansible_runner.run(
        private_data_dir="/home/yassine/dci/dci-pipeline/",
        playbook='%s/agent.yml' % stage['location'],
        verbosity=2,
        envvars=envvars,
        quiet=False)
    print(run.stats)

    return {
        'ocp_config': {
            'host': 'host.example.com',
            'worker': 'worker.example.com'}}


def run_cnf(stage, ocp_job_config, dci_credentials, envvars):
    # schedule job on topic with
    # ocp_job_config components
    # run cnf playbook with ocp config
    print('running cnf stage: %s' % stage['name'])
    envvars = dict(envvars)
    envvars.update(dci_credentials)
    extravars = {}
    extravars.update(ocp_job_config)
    run = ansible_runner.run(
        private_data_dir="/home/yassine/dci/dci-pipeline/",
        playbook='%s/agent.yml' % stage['location'],
        verbosity=2,
        envvars=envvars,
        extravars=extravars,
        quiet=False)
    print(run.stats)


def main():

    envvars = {
        'ANSIBLE_CALLBACK_PLUGINS': os.getenv(
            'ANSIBLE_CALLBACK_PLUGINS',
            '/home/yassine/dci/dci-ansible/callback')
    }
    pipeline = load_yaml_file('/home/yassine/dci/dci-pipeline/dcipipeline/pipeline.yml')
    check_pipeline(pipeline)

    ocp_stage = get_ocp_stage(pipeline)
    ocp_dci_credentials = load_yaml_file('%s/dci_credentials.yml' % ocp_stage['location'])
    ocp_job_config = run_ocp(ocp_stage, ocp_dci_credentials, envvars)

    cnf_stages = get_cnf_stages(pipeline)
    for cnf_stage in cnf_stages:
        dci_credentials = load_yaml_file('%s/dci_credentials.yml' % cnf_stage['location'])
        dci_credentials = {
            'DCI_CLIENT_ID': dci_credentials.get('DCI_CLIENT_ID'),
            'DCI_API_SECRET': dci_credentials.get('DCI_API_SECRET'),
            'DCI_CS_URL': dci_credentials.get('DCI_CS_URL')
        }

        run_cnf(cnf_stage, ocp_job_config, dci_credentials, envvars)


if __name__ == '__main__':
    main()
