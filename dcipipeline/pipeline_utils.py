# -*- coding: utf-8 -*-
#
# Copyright (C) 2021-2022 Red Hat, Inc
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

import sys

from dciclient.v1.api import job as dci_job


def get_job(context, job_id):
    print("getting info for job %s" % job_id, file=sys.stderr)
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


def get_pipeline_jobs(context, pipeline_id):
    print("pipeline_id=%s" % pipeline_id, file=sys.stderr)
    jobs = dci_job.list(
        context, sort="created_at", where="pipeline_id:%s" % pipeline_id
    )
    return [get_job(context, job["id"]) for job in jobs.json()["jobs"]]


def get_pipeline_from_job(context, job_id):
    initial_job = get_job(context, job_id)
    return get_pipeline_jobs(context, initial_job["pipeline_id"])
