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

import os
import sys
from argparse import ArgumentParser

from dciclient.printer import print_result
from dciclient.v1.api import job as dci_job
from dciclient.v1.api import pipeline as dci_pipeline
from dciclient.v1.shell_commands import context as dci_context

from dcipipeline import pipeline_utils as pu


def get_component_info(comp):
    if comp["type"] in ("rpm", "git"):
        c_type, c_name = comp["name"].split(" ", 1)
        return (c_type, c_name)
    else:
        return (comp["type"], comp["name"])


def parse_arguments(args, environment={}):
    p = ArgumentParser(
        prog="dci-diff-pipeline",
        description=(
            "Tool to compare components from 2 pipelines"
            "(https://docs.distributed-ci.io/dci-pipeline/#how-to-see-components-diff-between-two-pipelines)"
        ),
    )
    dci_context.parse_arguments(p, args, environment)
    p.add_argument(
        "--job_id_1",
        help="First job id",
        type=str,
        default=None,
    )
    p.add_argument(
        "--job_id_2",
        help="Second job id",
        type=str,
        default=None,
    )
    args = p.parse_args(args)

    return args


def search(args=sys.argv):
    args = parse_arguments(sys.argv[1:], os.environ)
    u_context = dci_context.build_context(args)

    if not u_context:
        print("Unable to authenticate. aborting", file=sys.stderr)
        sys.exit(2)

    if args.job_id_1 is None:
        print(
            "no job_id_1 provided, getting latest known job with a pipeline",
            file=sys.stderr,
        )
        pipelines = dci_pipeline.list(u_context, limit=10, offset=0).json()["pipelines"]
        for idx in range(len(pipelines)):
            pipeline_id = pipelines[idx]["id"]
            jobs = dci_job.list(
                u_context, limit=1, offset=0, where=f"pipeline_id:{pipeline_id}"
            ).json()["jobs"]
            if len(jobs) == 1:
                args.job_id_1 = jobs[0]["id"]
                break
        if args.job_id_1 is None:
            print("no job_id_1 found", file=sys.stderr)
            sys.exit(1)
    else:
        pipeline_id = None

    if args.job_id_2 is None:
        print("no job_id_2 provided, getting a similar job", file=sys.stderr)
        if pipeline_id is None:
            job1 = dci_job.get(u_context, args.job_id_1).json()["job"]
            pipeline_id = job1["pipeline_id"]
        if pipeline_id is None:
            print("No pipeline found", file=sys.stderr)
            sys.exit(1)
        pipeline_name = dci_pipeline.get(u_context, pipeline_id).json()["pipeline"][
            "name"
        ]
        pipelines = dci_pipeline.list(
            u_context, where=f"name:{pipeline_name}", limit=2, offset=0
        ).json()["pipelines"]
        jobs = dci_job.list(
            u_context, limit=1, offset=0, where=f"pipeline_id:{pipelines[1]['id']}"
        )
        if jobs.status_code == 200:
            if len(jobs.json()["jobs"]) > 0:
                args.job_id_2 = jobs.json()["jobs"][0]["id"]
                print("job id 2: %s" % args.job_id_2, file=sys.stderr)
            else:
                print("no job_id_2 found", file=sys.stderr)
                sys.exit(1)

    pipeline_1 = pu.get_pipeline_from_job(u_context, args.job_id_1)
    pipeline_2 = pu.get_pipeline_from_job(u_context, args.job_id_2)

    if len(pipeline_1) != len(pipeline_2):
        print("not the same pipeline structure", file=sys.stderr)
        sys.exit(1)

    pipeline_1_stages_types = set([j["data"]["pipeline"]["type"] for j in pipeline_1])
    pipeline_2_stages_types = set([j["data"]["pipeline"]["type"] for j in pipeline_2])

    if pipeline_1_stages_types != pipeline_2_stages_types:
        print(
            "not the same pipeline types: pipeline_1=%s,pipeline_2=%s"
            % (pipeline_1_stages_types, pipeline_2_stages_types),
            file=sys.stderr,
        )
        sys.exit(1)

    pt = []
    for i in range(0, len(pipeline_1)):
        components_1 = {}
        components_2 = {}
        for c in pu.get_job_components(u_context, pipeline_1[i]["id"]):
            c_type, c_name = get_component_info(c)
            components_1[c_type] = c_name
        for c in pu.get_job_components(u_context, pipeline_2[i]["id"]):
            c_type, c_name = get_component_info(c)
            components_2[c_type] = c_name
        for c1 in components_1:
            if c1 in components_2:
                if components_1[c1] != components_2[c1]:
                    pt.append(
                        {
                            "name": c1,
                            "pipeline": pipeline_1[i]["data"]["pipeline"]["name"],
                            "component job 1": components_1[c1],
                            "component job 2": components_2[c1],
                        }
                    )
            else:
                pt.append(
                    {
                        "name": c1,
                        "pipeline": pipeline_1[i]["data"]["pipeline"]["name"],
                        "component job 1": components_1[c1],
                        "component job 2": "Not found",
                    }
                )
        for c2 in components_2:
            if c2 not in components_1:
                pt.append(
                    {
                        "name": c2,
                        "pipeline": pipeline_1[i]["data"]["pipeline"]["name"],
                        "component job 1": "Not found",
                        "component job 2": components_2[c2],
                    }
                )
    print_result(
        pt,
        args.format,
        args.verbose,
        ["name", "pipeline", "component job 1", "component job 2"],
    )


def main(args=sys.argv):
    try:
        return search(args)
    except Exception as ex:
        print(f"Unable to perform search: {ex}", file=sys.stderr)
        return 1
