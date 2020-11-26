#!/usr/bin/env python
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
# under the License.

from dciclient.v1.api import context as dci_context
from dciclient.v1.api import job as dci_job

import sys
import yaml
import pprint


def get_job(context, job_id):
    j = dci_job.get(context, job_id)
    if j.status_code == 200:
        return j.json()['job']
    else:
        print("get_job error: %s" % j.text)


def is_ocp_job(context, job):
    return 'type:ocp' in job['tags']


def get_cnf_jobs(context, ocp_job_id):
    j = dci_job.list(context, where='tags:prev-job:%s' % ocp_job_id)
    if j.status_code == 200:
        return j.json()['jobs']
    else:
        print("get_cnf_jobs error: %s" % j.text)


def get_ocp_job_id(context, job_id):
    j = dci_job.get(context, job_id)
    if j.status_code == 200:
        for t in j.json()['job']['tags']:
            if t.startswith('prev-job'):
                return t.split(':', 1)[-1]
    else:
        print("get_job error: %s" % j.text)


def build_pipeline(ocp_job, cnf_jobs):
    ocp_job = ocp_job['data']['pipeline']
    cnf_jobs = [c['data']['pipeline'] for c in cnf_jobs]
    with open('./rebuilt-pipeline.yml', 'w') as f:
        yaml.dump(
            [ocp_job] + cnf_jobs,
            f,
            default_flow_style=False)


def main(args=sys.argv):
    r_context = dci_context.build_signature_context()
    job_id = sys.argv[1]
    initial_job = get_job(r_context, job_id)
    ocp_job = None
    cnf_jobs = []
    if is_ocp_job(r_context, initial_job):
        ocp_job = initial_job
        cnf_jobs = get_cnf_jobs(r_context, ocp_job)
    else:
        ocp_job_id = get_ocp_job_id(r_context, job_id)
        ocp_job = get_job(r_context, ocp_job_id)
        cnf_jobs = get_cnf_jobs(r_context, ocp_job_id)
    
    build_pipeline(ocp_job, cnf_jobs)


if __name__ == "__main__":
    sys.exit(main())
