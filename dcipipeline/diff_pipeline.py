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
from prettytable import PrettyTable
import sys


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
        if len(sys.argv) < 3:
            print("usage: %s <job-id1> <job-id2>" % sys.argv[0])
            sys.exit(1)
        job_id_1 = sys.argv[1]
        job_id_2 = sys.argv[2]
    else:
        print(
            "using local development environment with dci_login: pipeline-user, dci_cs_url: http://127.0.0.1:5000"
        )
        u_context = dci_context.build_dci_context(
            dci_cs_url="http://127.0.0.1:5000/",
            dci_login="pipeline-user",
            dci_password="pipeline-user",
        )

        if len(sys.argv) < 3:
            print("no job ids provided, getting latest known job")
            jobs = dci_job.list(u_context, limit=1, offset=0)
            if jobs.status_code == 200:
                if len(jobs.json()["jobs"]) > 0:
                    job_id_1 = jobs.json()["jobs"][0]["id"]
                    job_id_2 = job_id_1
                    print("job id 1: %s" % job_id_1)
                    print("job id 1: %s" % job_id_2)
                else:
                    print("no job found")
                    sys.exit(1)

    pipeline_1 = pu.get_pipeline_from_job(u_context, job_id_1)
    pipeline_2 = pu.get_pipeline_from_job(u_context, job_id_2)

    if len(pipeline_1) != len(pipeline_2):
        print("not the same pipeline structure")
        sys.exit(1)

    pipeline_1_stages_types = set([j["data"]["pipeline"]["type"] for j in pipeline_1])
    pipeline_2_stages_types = set([j["data"]["pipeline"]["type"] for j in pipeline_2])

    if pipeline_1_stages_types != pipeline_2_stages_types:
        print(
            "not the same pipeline types: pipeline_1=%s,pipeline_2=%s"
            % (pipeline_1_stages_types, pipeline_2_stages_types)
        )
        sys.exit(1)

    pt = PrettyTable()
    pt.field_names = [
        "\033[95m pipeline 1 \033[0m",
        "\033[95m pipeline 2 \033[0m",
        "\033[95m stage \033[0m",
        "\033[95m component type \033[0m",
        "\033[95m component 1 \033[0m",
        "\033[95m component 2 \033[0m",
    ]

    for i in range(0, len(pipeline_1)):
        components_1 = pu.get_job_components(u_context, pipeline_1[i]["id"])
        components_2 = pu.get_job_components(u_context, pipeline_2[i]["id"])
        for c1 in components_1:
            c_type = c1["type"]
            for c2 in components_2:
                if c_type == c2["type"]:
                    if c1["name"] != c2["name"]:
                        pt.add_row(
                            [
                                pipeline_1[i]["id"],
                                pipeline_2[i]["id"],
                                pipeline_1[i]["data"]["pipeline"]["name"],
                                c_type,
                                "\033[91m %s \033[0m" % c1["name"],
                                "\033[91m %s \033[0m" % c2["name"],
                            ]
                        )
    print(pt)


if __name__ == "__main__":
    sys.exit(main())
