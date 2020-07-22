# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Red Hat, Inc
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

from dciclient.v1.api import component as dci_component
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
    with open(path) as file:
        return yaml.load(file, Loader=yaml.SafeLoader)


def generate_ansible_cfg(dci_ansible_dir, config_dir):
    fname = os.path.join(config_dir, 'ansible.cfg')
    log.info('Generating %s using dci_ansible_dir=%s' % (fname, dci_ansible_dir))
    with open(fname, 'w') as f:
        f.write('''[defaults]
library            = {dci_ansible_dir}/modules/
module_utils       = {dci_ansible_dir}/module_utils/
callback_whitelist = dci
callback_plugins   = {dci_ansible_dir}/callback/
interpreter_python = /usr/bin/python2

'''.format(dci_ansible_dir=dci_ansible_dir))


def get_types_of_stage(pipeline):
    names = []
    for stage in pipeline:
        if stage['type'] not in names:
            names.append(stage['type'])
    return names


def get_stages(stage_type, pipeline):
    stages = []
    for stage in pipeline:
        if stage['type'] == stage_type:
            stages.append(stage)
    return stages


def get_stage_by_name(name, pipeline):
    if name:
        for stage in pipeline:
            if stage['name'] == name:
                return stage
    return None


def build_context(dci_credentials):
    return dci_context.build_signature_context(
        dci_client_id=dci_credentials['DCI_CLIENT_ID'],
        dci_api_secret=dci_credentials['DCI_API_SECRET'],
        dci_cs_url=dci_credentials['DCI_CS_URL']
    )


def get_components(context, stage, topic_id, tag=None):
    components = []
    for component_name in stage['components']:
        resp = dci_topic.list_components(context, topic_id,
                                         limit=1,
                                         offset=0,
                                         sort='-created_at',
                                         where='type:%s%s' % (component_name,
                                                              ',tags:%s' % tag if tag else ''))
        if resp.status_code == 200:
            log.info('Got component %s: %s' % (component_name, resp.text))
            if resp.json()['_meta']['count'] > 0:
                components.append(resp.json()['components'][0])
            else:
                log.error('No %s component' % component_name)
        else:
            log.error('Unable to fetch component %s for topic %s: %s' % (component_name,
                                                                         stage['topic'],
                                                                         resp.text))
    return components


def get_topic_id(context, stage):
    topic_res = dci_topic.list(context, where='name:' + stage['topic'])
    if topic_res.status_code == 200:
        topics = topic_res.json()['topics']
        log.debug('topics: %s' % topics)
        if len(topics) == 0:
            log.error('topic %s not found' % stage['topic'])
            return None
        return topics[0]['id']
    else:
        log.error('Unable to get topic %s: %s' % (stage['topic'], topic_res.text))
    return None


def schedule_job(stage, context, tag=None):
    log.info('scheduling job %s on topic %s%s' % (stage['name'], stage['topic'],
                                                  ' with tag %s' % tag if tag else ''))

    topic_id = get_topic_id(context, stage)
    components = get_components(context, stage, topic_id, tag)

    if len(stage['components']) != len(components):
        log.error('Unable to get all components %d out of %d' % (len(components), len(stage['components'])))
        return None

    schedule = dci_job.create(context, topic_id, comment=stage['name'],
                              components=[c['id'] for c in components])
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
    return None


def add_tags_to_job(job_id, tags, context):
    for tag in tags:
        log.info('Setting tag %s on job %s' % (tag, job_id))
        dci_job.add_tag(context, job_id, tag)


def add_tag_to_component(component_id, tag, context):
    log.info('Setting tag %s on component %s' % (tag, component_id))
    dci_component.add_tag(context, component_id, tag)


def run_stage(stage, dci_credentials, envvars, data_dir, job_info):
    shutil.rmtree('%s/env' % data_dir, ignore_errors=True)
    log.info('running stage: %s' % stage['name'])
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
    return run.rc == 0


def get_config(args):
    dci_ansible_dir = os.getenv('DCI_ANSIBLE_DIR', os.path.join(os.path.dirname(TOPDIR), 'dci-ansible'))
    envvars = {
        'ANSIBLE_CALLBACK_PLUGINS': os.path.join(dci_ansible_dir, 'callback'),
    }
    config = args[1] if len(args) > 1 else os.path.join(TOPDIR, 'dcipipeline/pipeline.yml')
    config_dir = os.path.dirname(config)
    pipeline = load_yaml_file(config)
    generate_ansible_cfg(dci_ansible_dir, config_dir)
    return config_dir, pipeline, envvars


def set_success_tag(stage, job_info, context):
    if 'success_tag' in stage:
        for component in job_info['job']['components']:
            add_tag_to_component(component['id'], stage['success_tag'], context)


def create_inputs(config_dir, prev_stage, stage):
    if 'inputs' in stage:
        for key in stage['inputs']:
            log.info('Copying %s/%s into %s/%s' % (config_dir, prev_stage['outputs'][key],
                                                   config_dir, stage['inputs'][key]))
            with open(os.path.join(config_dir, stage['inputs'][key]), 'wb') as ofile:
                with open(os.path.join(config_dir, prev_stage['outputs'][key]), 'rb') as ifile:
                    ofile.write(ifile.read())


def run_stages(stage_type, pipeline, config_dir, envvars):
    stages = get_stages(stage_type, pipeline)
    for stage in stages:
        dci_credentials = load_yaml_file('%s/%s/dci_credentials.yml' % (config_dir, stage['location']))
        dci_context = build_context(dci_credentials)

        prev_stage = get_stage_by_name(stage.get('prev'), pipeline)
        create_inputs(config_dir, prev_stage, stage)

        job_info = schedule_job(stage, dci_context)

        if not job_info:
            log.error('Unable to schedule job %s. Skipping' % stage['name'])
            continue

        tags = [stage['topic']]
        if prev_stage and 'job_info' in prev_stage:
            log.info('prev stage: %s' % prev_stage)
            for component in prev_stage['job_info']['job']['components']:
                tags.append('%s/%s' % (prev_stage['topic'], component['name']))
        add_tags_to_job(job_info['job']['id'], tags, dci_context)

        if run_stage(stage, dci_credentials, envvars, config_dir, job_info):
            set_success_tag(stage, job_info, dci_context)
        else:
            log.error('Unable to run successfully job %s' % stage['name'])
            if 'fallback_last_success' in stage:
                log.info('Retrying with tag %s' % stage['fallback_last_success'])
                job_info = schedule_job(stage, dci_context, stage['fallback_last_success'])
                if run_stage(stage, dci_credentials, envvars, config_dir, job_info):
                    set_success_tag(stage, job_info, dci_context)
                else:
                    log.error('Unable to run successfully job %s on tag %s' % (stage['name'],
                                                                               stage['fallback_last_success']))
        stage['job_info'] = job_info


def main(args):
    config_dir, pipeline, envvars = get_config(args)

    for stage_type in get_types_of_stage(pipeline):
        run_stages(stage_type, pipeline, config_dir, envvars)


if __name__ == '__main__':
    main(sys.argv)
