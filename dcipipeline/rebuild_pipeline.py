# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Red Hat, Inc
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

import yaml
from dciclient.v1.api import job as dci_job
from dciclient.v1.shell_commands import context as dci_context

from dcipipeline import pipeline_utils as pu


def save_pipeline(pipeline_jobs, pipeline_filename):
    pipeline = [pj["data"]["pipeline"] for pj in pipeline_jobs]
    with open(pipeline_filename, "w") as f:
        yaml.dump(pipeline, f, default_flow_style=False)


def update_pipeline_with_component_version(context, pipeline_jobs):
    for pj in pipeline_jobs:
        components = pu.get_stage_components(context, pj["id"])
        pj["data"]["pipeline"]["components"] = components


def parse_arguments(args, environment={}):
    p = ArgumentParser(
        prog="dci-rebuild-pipeline",
        description=(
            "Tool to rebuild a pipeline from the info of a DCI job"
            "(https://docs.distributed-ci.io/dci-pipeline/#how-to-rebuild-a-pipeline)"
        ),
    )
    dci_context.parse_arguments(p, args, environment)
    p.add_argument(
        "--job_id",
        help="DCI job id",
        type=str,
        default=None,
        required=False,
    )
    p.add_argument(
        "--pipeline_filename",
        help="Pipeline filename to write to",
        type=str,
        default="./rebuilt-pipeline.yml",
        required=False,
    )
    args = p.parse_args(args)

    return args


def main(args=sys.argv):
    args = parse_arguments(sys.argv[1:], os.environ)
    u_context = dci_context.build_context(args)

    if not u_context:
        print("Unable to authenticate. aborting")
        sys.exit(2)

    if args.job_id is None:
        print("no job id provided, getting latest known job")
        jobs = dci_job.list(u_context, limit=1, offset=0)
        if jobs.status_code == 200:
            if len(jobs.json()["jobs"]) > 0:
                args.job_id = jobs.json()["jobs"][0]["id"]
                print("job id: %s" % args.job_id)
            else:
                print("no job found")
                sys.exit(1)
        else:
            job_id = sys.argv[1]
            print("job id: %s" % job_id)

    pipeline_jobs = pu.get_pipeline_from_job(u_context, args.job_id)

    update_pipeline_with_component_version(u_context, pipeline_jobs)

    save_pipeline(pipeline_jobs, args.pipeline_filename)

    print(
        "pipeline rebuilt successfully, please see the '%s' file"
        % args.pipeline_filename
    )


if __name__ == "__main__":
    sys.exit(main())
