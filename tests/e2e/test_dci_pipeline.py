#
# Copyright (C) 2021 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from dcipipeline.main import main, PIPELINE

import os
import requests
import sys
import time

TOPDIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.basename(__file__))))

DCI_LOGIN = os.environ.get("DCI_LOGIN", "admin")
DCI_PASSWORD = os.environ.get("DCI_PASSWORD", "admin")
DCI_CS_URL = os.environ.get("DCI_CS_URL", "http://127.0.0.1:5000")


def check_return(response):
    print(response)
    if response.status_code // 100 != 2:
        raise Exception(response.text)
    return response


def get_url(endpoint, subresource=None):
    return "%s/api/v1/%s" % (DCI_CS_URL, endpoint)


def get(
    endpoint,
    user=(
        DCI_LOGIN,
        DCI_PASSWORD,
    ),
):
    url = get_url(endpoint)
    return check_return(requests.get(url, auth=user))


def get_jobs():
    teams = get("jobs").json()["jobs"]
    return teams


def p(pname):
    return os.path.join(TOPDIR, "dcipipeline", pname)


def test_dci_pipeline():
    jobs = get_jobs()
    rc = main(["dci-pipeline", p("pipeline.yml")])
    assert rc == 0
    assert len(PIPELINE) == 2
    jobs2 = get_jobs()
    assert len(jobs) + 2 == len(jobs2)


def test_dci_pipeline_edge():
    rc = main(["dci-pipeline", p("pipeline-edge.yml")])
    assert rc == 0


def test_dci_pipeline_retry():
    rc = main(["dci-pipeline", p("pipeline-edge.yml")])
    assert rc == 0


def test_dci_pipeline_skip():
    rc = main(
        [
            "dci-pipeline",
            "openshift-vanilla:ansible_skip_tags=broken",
            p("pipeline-retry.yml"),
            p("cnf-pipeline.yml"),
        ]
    )
    assert rc == 0


def test_dci_pipeline_upgrade():
    rc = main(["dci-pipeline", p("upgrade-pipeline.yml")])
    assert rc == 0


def test_dci_pipeline_sigterm():
    jobs = get_jobs()
    pid = os.fork()

    if pid == 0:
        os.system("cd %s; dci-pipeline dcipipeline/pipeline-pause.yml")
    else:
        time.sleep(10)
        os.system("killall dci-pipeline")
        time.sleep(10)

        jobs2 = get_jobs()
        assert len(jobs) + 1 == len(jobs2)
        assert jobs2[0]["status"] == "error"
