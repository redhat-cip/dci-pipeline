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

from dciclient.v1.api import job as dci_job

import sys


def get_job(context, job_id):
    j = dci_job.get(context, job_id)
    if j.status_code == 200:
        return j.json()["job"]
    else:
        print("get_job error: %s" % j.text)
        sys.exit(1)


def get_job_components(context, job_id):
    c = dci_job.get_components(context, job_id)
    if c.status_code == 200:
        return c.json()["components"]
    else:
        print("get_job_components error: %s" % c.text)
        sys.exit(1)


def get_stage_components(context, job_id):
    c = dci_job.get_components(context, job_id)
    if c.status_code == 200:
        components = c.json()["components"]
        return ["%s=%s" % (c["type"], c["name"]) for c in components]
    else:
        print("get_stage_components error: %s" % c.text)
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
            _job_id = j.json()["jobs"][0]["id"]
            return get_job(context, _job_id)
        else:
            return None
    else:
        print("get_next_job_id error: %s" % j.text)
        sys.exit(1)


def get_next_jobs(context, job):
    next_jobs = []
    _current_job = job
    while True:
        next_job = get_next_job(context, _current_job)
        if not next_job:
            break
        next_jobs.append(next_job)
        _current_job = next_job
    return next_jobs


def get_pipeline_from_job(context, job_id):
    initial_job = get_job(context, job_id)
    previous_jobs = get_previous_jobs(context, initial_job)
    next_jobs = get_next_jobs(context, initial_job)

    pipeline_jobs = previous_jobs
    pipeline_jobs.append(initial_job)
    pipeline_jobs.extend(next_jobs)

    return pipeline_jobs
