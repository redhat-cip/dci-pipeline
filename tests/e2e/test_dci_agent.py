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

import os

import requests

from dciagent.main import main

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
    teams = get("jobs?embed=components").json()["jobs"]
    return teams


def p(pname):
    return os.path.join(TOPDIR, "dciagent", "tests", "data", pname)


def test_dci_agent_ctl():
    jobs = get_jobs()
    os.environ["DCI_QUEUE_JOBID"] = "12"
    rc = main(
        [
            "dci-agent-ctl",
            "openshift-vanilla:components=ocp=ocp-4.8.0-0.nightly-20200703",
            p("settings.yml"),
        ]
    )
    assert rc == 0
    jobs2 = get_jobs()
    assert len(jobs) + 1 == len(jobs2)
    assert jobs2[0]["configuration"] == "myconf"
    assert jobs2[0]["url"] == "https://lwn.net/"
    assert jobs2[0]["name"] == "openshift-vanilla"
    ocp_component = [comp for comp in jobs2[0]["components"] if comp["type"] == "ocp"]
    assert (
        len(ocp_component) == 1
        and ocp_component[0]["name"] == "ocp-4.8.0-0.nightly-20200703"
    )
