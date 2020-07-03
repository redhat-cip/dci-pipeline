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

from dciclient.v1.api import job as dci_job
from dciclient.v1.api import jobstate as dci_jobstate
from dciclient.v1.api import topic as dci_topic
from dciclient.v1.api import context as dci_context

import ansible_runner

import logging
import os
import shutil
import sys
import yaml


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)
VERBOSE_LEVEL = 2
TOPDIR = os.getenv('DCI_PIPELINE_TOPDIR',
                   os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_yaml_file(path):
    with open(path, 'r') as file:
        try:
            return yaml.load(file, Loader=yaml.SafeLoader)
        except yaml.YAMLError as exc:
            print(exc)
            sys.exit(1)


def check_pipeline(pipeline):
    def _check_agent_directory(path):
        log.info('check agent directory at %s' % path)
        pass


def generate_ansible_cfg(dci_ansible_dir, config_dir):
    with open(os.path.join(config_dir, 'ansible.cfg'), 'w') as f:
        f.write('''[defaults]
library            = {dci_ansible_dir}/modules/
module_utils       = {dci_ansible_dir}/module_utils/
callback_whitelist = dci
callback_plugins   = {dci_ansible_dir}/callback/
interpreter_python = /usr/bin/python2

'''.format(dci_ansible_dir=dci_ansible_dir))


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


def schedule_job(topic_name, dci_credentials):
    context = dci_context.build_signature_context(
        dci_client_id=dci_credentials['DCI_CLIENT_ID'],
        dci_api_secret=dci_credentials['DCI_API_SECRET'],
        dci_cs_url=dci_credentials['DCI_CS_URL']
    )
    log.info('scheduling job on topic %s' % topic_name)

    topic_res = dci_topic.list(context, where='name:' + topic_name)
    if topic_res.status_code == 200:
        topics = topic_res.json()['topics']
        log.debug('topics: %s' % topics)
        if len(topics) == 0:
            log.error('topic %s not found' % topic_name)
            sys.exit(1)
        topic_id = topics[0]['id']
        schedule = dci_job.schedule(context, topic_id=topic_id)
        if schedule.status_code == 201:
            scheduled_job_id = schedule.json()['job']['id']
            scheduled_job = dci_job.get(
                context, scheduled_job_id, embed='topic,remoteci,components')
            if scheduled_job.status_code == 200:
                job_id = scheduled_job.json()['job']['id']
                dci_jobstate.create(
                    context,
                    status='new',
                    comment='job scheduled',
                    job_id=job_id)
                return scheduled_job.json()
            else:
                log.error('error getting schedule info: %s' % scheduled_job.text)
        else:
            log.error('error scheduling: %s' % schedule.text)
    else:
        log.error('error getting the list of topics: %s' % topic_res.text)
    return None


def add_tags_to_job(job_id, tags, dci_credentials):
    context = dci_context.build_signature_context(
        dci_client_id=dci_credentials['DCI_CLIENT_ID'],
        dci_api_secret=dci_credentials['DCI_API_SECRET'],
        dci_cs_url=dci_credentials['DCI_CS_URL']
    )

    for tag in tags:
        dci_job.add_tag(context, job_id, tag)


def run_ocp(stage, dci_credentials, envvars, data_dir, job_info):
    # schedule job on topic
    # run ocp playbook with job_info
    # return job_info
    log.info('running ocp stage: %s' % stage['name'])
    envvars = dict(envvars)
    envvars.update(dci_credentials)
    extravars = {'job_info': job_info}
    run = ansible_runner.run(
        private_data_dir=data_dir,
        playbook='%s/agent.yml' % stage['location'],
        verbosity=VERBOSE_LEVEL,
        envvars=envvars,
        extravars=extravars,
        quiet=False)
    log.info(run.stats)

    return {
        'ocp_config': {
            'host': 'host.example.com',
            'worker': 'worker.example.com',
            'job_info': job_info}}


def run_cnf(stage, ocp_job_config, dci_credentials, envvars, data_dir, job_info):
    # schedule job on topic with
    # ocp_job_config components
    # run cnf playbook with ocp config
    log.info('running cnf stage: %s' % stage['name'])
    envvars = dict(envvars)
    envvars.update(dci_credentials)
    extravars = {'job_info': job_info}
    extravars.update(ocp_job_config)
    run = ansible_runner.run(
        private_data_dir=data_dir,
        playbook='%s/agent.yml' % stage['location'],
        verbosity=VERBOSE_LEVEL,
        envvars=envvars,
        extravars=extravars,
        quiet=False)
    log.info(run.stats)


def main():
    dci_ansible_dir = os.getenv('DCI_ANSIBLE_DIR', os.path.join(os.path.dirname(TOPDIR), 'dci-ansible'))
    envvars = {
        'ANSIBLE_CALLBACK_PLUGINS': os.path.join(dci_ansible_dir, 'callback'),
    }
    config = sys.argv[1] if len(sys.argv) > 1 else os.path.join(TOPDIR, 'dcipipeline/pipeline.yml')
    config_dir = os.path.dirname(config)
    pipeline = load_yaml_file(config)
    check_pipeline(pipeline)

    shutil.rmtree('%s/env' % config_dir, ignore_errors=True)
    generate_ansible_cfg(dci_ansible_dir, config_dir)
    ocp_stage = get_ocp_stage(pipeline)
    ocp_dci_credentials = load_yaml_file('%s/%s/dci_credentials.yml' % (config_dir, ocp_stage['location']))
    ocp_job_info = schedule_job(ocp_stage['topic'], ocp_dci_credentials)
    if not ocp_job_info:
        log.error('error when scheduling a job')
        sys.exit(1)

    ocp_job_config = run_ocp(ocp_stage, ocp_dci_credentials, envvars, config_dir, ocp_job_info)

    cnf_stages = get_cnf_stages(pipeline)
    for cnf_stage in cnf_stages:
        dci_credentials = load_yaml_file('%s/%s/dci_credentials.yml' % (config_dir, cnf_stage['location']))
        dci_credentials = {
            'DCI_CLIENT_ID': dci_credentials.get('DCI_CLIENT_ID'),
            'DCI_API_SECRET': dci_credentials.get('DCI_API_SECRET'),
            'DCI_CS_URL': dci_credentials.get('DCI_CS_URL')
        }
        shutil.rmtree('%s/env' % config_dir, ignore_errors=True)
        cnf_job_info = schedule_job(cnf_stage['topic'], dci_credentials)

        if not cnf_job_info:
            log.error('Unable to schedule job %s. Skipping' % cnf_stage)
            continue
        tags = ['RH-CNF']
        for component in ocp_job_info['job']['components']:
            tags.append('%s/%s' % (ocp_stage['topic'], component['name']))
        add_tags_to_job(cnf_job_info['job']['id'], tags, dci_credentials)
        if not cnf_job_info:
            log.error('error when scheduling a job')
            sys.exit(1)
        run_cnf(cnf_stage, ocp_job_config, dci_credentials, envvars, config_dir, cnf_job_info)

    shutil.rmtree('%s/env' % config_dir, ignore_errors=True)


if __name__ == '__main__':
    main()
