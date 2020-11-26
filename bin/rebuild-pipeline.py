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


def save_pipeline(pipeline_jobs):
    pipeline = [pj["data"]["pipeline"] for pj in pipeline_jobs]
    pprint.pprint(pipeline)
    with open("./rebuilt-pipeline.yml", "w") as f:
        yaml.dump(pipeline, f, default_flow_style=False)


def get_job(context, job_id):
    print(job_id)
    j = dci_job.get(context, job_id)
    if j.status_code == 200:
        return j.json()["job"]
    else:
        print("get_job error: %s" % j.text)
        sys.exit(1)


def get_previous_job_id(job):
    for t in job["tags"]:
        if t.startswith("prev-job"):
            return t.split(":")[1]
    return None


def get_previous_jobs(context, job):
    _current_job = job
    previous_jobs = []
    while True:
        prev_job_id = get_previous_job_id(_current_job)
        if not prev_job_id:
            break
        prev_job = get_job(context, prev_job_id)
        previous_jobs.append(prev_job)
        _current_job = prev_job
    return previous_jobs[::-1]


def get_next_job(context, job):
    j = dci_job.list(context, where="tags:prev-job:%s" % job["id"])
    if j.status_code == 200:
        if len(j.json()["jobs"]) > 0:
            return j.json()["jobs"][0]
        else:
            return None
    else:
        print("get_next_job_id error: %s" % j.text)
        sys.exit(1)


def get_next_jobs(context, job):
    next_jobs = []
    while True:
        next_job = get_next_job(context, job)
        if not next_job:
            break
        next_jobs.append(next_job)
    return next_jobs[::-1]


def main(args=sys.argv):
    print("use pipeline user account")
    u_context = dci_context.build_dci_context(
        dci_cs_url="http://127.0.0.1:5000/",
        dci_login="pipeline-user",
        dci_password="pipeline-user",
    )
    job_id = sys.argv[1]

    initial_job = get_job(u_context, job_id)
    previous_jobs = get_previous_jobs(u_context, initial_job)
    next_jobs = get_next_jobs(u_context, initial_job)

    pipeline_jobs = previous_jobs
    pipeline_jobs.append(initial_job)
    pipeline_jobs.extend(next_jobs)

    save_pipeline(pipeline_jobs)


if __name__ == "__main__":
    sys.exit(main())
