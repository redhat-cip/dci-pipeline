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
from dcipipeline import pipeline_utils as pu

import os
import sys
import yaml


def save_pipeline(pipeline_jobs):
    pipeline = [pj["data"]["pipeline"] for pj in pipeline_jobs]
    with open("./rebuilt-pipeline.yml", "w") as f:
        yaml.dump(pipeline, f, default_flow_style=False)


def update_pipeline_with_component_version(context, pipeline_jobs):
    for pj in pipeline_jobs:
        job_id = pj["id"]
        components = pu.get_stage_components(context, job_id)
        pj["data"]["pipeline"]["components"] = components


def main(args=sys.argv):

    u_context = None

    if os.getenv("DCI_LOGIN") and os.getenv("DCI_PASSWORD") and os.getenv("DCI_CS_URL"):
        print(
            "using environment with dci_login: %s, dci_cs_url: %s"
            % (os.getenv("DCI_LOGIN"), os.getenv("DCI_CS_URL"))
        )
        u_context = dci_context.build_dci_context(
            dci_cs_url=os.getenv("DCI_CS_URL"),
            dci_login=os.getenv("DCI_LOGIN"),
            dci_password=os.getenv("DCI_PASSWORD"),
        )

    if (
        not u_context
        and os.getenv("DCI_CLIENT_ID")
        and os.getenv("DCI_API_SECRET")
        and os.getenv("DCI_CS_URL")
    ):
        print(
            "using environment with dci_client_id: %s, dci_cs_url: %s"
            % (os.getenv("DCI_LOGIN"), os.getenv("DCI_CS_URL"))
        )
        u_context = dci_context.build_signature_context(
            dci_cs_url=os.getenv("DCI_CS_URL"),
            dci_client_id=os.getenv("DCI_CLIENT_ID"),
            dci_api_secret=os.getenv("DCI_API_SECRET"),
        )

    if os.getenv("DCI_CS_URL"):
        print("using environment %s" % os.getenv("DCI_CS_URL"))
        if len(sys.argv) < 2:
            print("usage: %s <job-id>" % sys.argv[0])
            sys.exit(1)

    if not os.getenv("DCI_CS_URL"):
        print(
            "using local development environmen with dci_login: pipeline-user, dci_cs_url: http://127.0.0.1:5000"
        )
        u_context = dci_context.build_dci_context(
            dci_cs_url="http://127.0.0.1:5000/",
            dci_login="pipeline-user",
            dci_password="pipeline-user",
        )
        if len(sys.argv) < 2:
            print("no job id provided, getting latest known job")
            jobs = dci_job.list(u_context, limit=1, offset=0)
            if jobs.status_code == 200:
                if len(jobs.json()["jobs"]) > 0:
                    job_id = jobs.json()["jobs"][0]["id"]
                    print("job id: %s" % job_id)
                else:
                    print("no job found")
                    sys.exit(1)
        else:
            job_id = sys.argv[1]
            print("job id: %s" % job_id)

    pipeline_jobs = pu.get_pipeline_from_job(u_context, job_id)

    update_pipeline_with_component_version(u_context, pipeline_jobs)

    save_pipeline(pipeline_jobs)

    print("pipeline rebuilt successfully, please see the 'rebuilt-pipeline.yml' file")


if __name__ == "__main__":
    sys.exit(main())
