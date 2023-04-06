#
# Copyright (C) 2021-2023 Red Hat, Inc.
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
import signal
import subprocess
import sys
import time

import pytest
import requests

from dcipipeline.main import PIPELINE
from dcipipeline.main import main as dci_main

TOPDIR = os.path.abspath(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.basename(__file__))))
)

DCI_LOGIN = os.environ.get("DCI_LOGIN", "admin")
DCI_PASSWORD = os.environ.get("DCI_PASSWORD", "admin")
DCI_CS_URL = os.environ.get("DCI_CS_URL", "http://127.0.0.1:5000")


def main(args):
    sys.stderr.write("+ {}\n".format(" ".join(args)))
    return dci_main(args)


def check_return(response):
    print(response, file=sys.stderr)
    if response.status_code // 100 != 2:
        raise Exception(response.text)
    return response


def get_url(endpoint):
    return "%s/api/v1/%s" % (DCI_CS_URL, endpoint)


def get(
    endpoint,
    user=(
        DCI_LOGIN,
        DCI_PASSWORD,
    ),
):
    url = get_url(endpoint)
    print("GET %s" % url, file=sys.stderr)
    return check_return(requests.get(url, auth=user))


def get_jobs():
    teams = get("jobs?embed=components&sort=-created_at").json()
    return teams["jobs"], teams["_meta"]["count"]


def get_ocp_component_id(topic):
    topics = get("topics?where=name:%s" % topic).json()
    print(topics, file=sys.stderr)
    components = get(
        "topics/%s/components?where=type:ocp" % topics["topics"][0]["id"]
    ).json()
    return components["components"][0]["id"]


def p(pname):
    return os.path.join(TOPDIR, "dcipipeline", pname)


def test_dci_pipeline():
    jobs, count = get_jobs()
    os.environ["DCI_QUEUE_JOBID"] = "12"
    rc = main(
        [
            "dci-pipeline",
            "openshift-vanilla:components=ocp=4.8.0-0.nightly-20200703",
            p("pipeline.yml"),
        ]
    )
    assert rc == 0
    assert len(PIPELINE) == 2
    jobs2, count2 = get_jobs()
    assert count + 2 == count2
    assert jobs2[0]["previous_job_id"] == jobs2[1]["id"]
    assert jobs2[0]["name"] == "rh-cnf"
    assert jobs2[1]["configuration"] == "myconf"
    assert jobs2[1]["url"] == "https://lwn.net/"
    assert jobs2[1]["name"] == "openshift-vanilla"
    ocp_component = [comp for comp in jobs2[1]["components"] if comp["type"] == "ocp"]
    assert (
        len(ocp_component) == 1
        and ocp_component[0]["version"] == "4.8.0-0.nightly-20200703"
    )
    tags = {d.split(":")[0]: d.split(":")[1] for d in jobs2[0]["tags"]}
    assert "pipeline-id" in tags


def test_dci_pipeline_edge():
    inventory = p("agents/rh-cnf/inventory2.yml")
    out = subprocess.check_output(
        ". cnf-telco-ci.sh; echo -n 42|dci-vault encrypt",
        shell=True,
        universal_newlines=True,
        executable="/bin/bash",  # it doesn't work with /bin/sh
    )
    prefix = "      "
    aligned = prefix + out.replace("\n", "\n" + prefix)
    with open(inventory, "w") as fp:
        fp.write(
            """all:
  vars:
    answer: !vault |
%s
"""
            % aligned
        )
    rc = main(
        [
            "dci-pipeline",
            p("pipeline-edge.yml"),
            "rh-cnf:ansible_inventory=" + inventory,
            "openshift-edge:ansible_extravars=answer:42",
        ]
    )
    assert rc == 0


def test_dci_pipeline_edge2():
    pipeline = p("pipeline-edge.yml")
    pipeline2 = p("pipeline-edge2.yml")
    out = subprocess.check_output(
        ". rh-telco-pipeline.sh; echo -n 42|dci-vault encrypt",
        shell=True,
        universal_newlines=True,
        executable="/bin/bash",  # it doesn't work with /bin/sh
    )
    prefix = "        "
    aligned = prefix + out.replace("\n", "\n" + prefix)
    content = (
        open(pipeline).read(-1).replace("var: 43", "answer: !vault |\n%s" % aligned)
    )
    with open(pipeline2, "w") as fp:
        fp.write(content)
    rc = main(
        [
            "dci-pipeline",
            pipeline2,
        ]
    )
    assert rc == 0


@pytest.mark.skip(
    reason="No way to make it work. Failing to load community.general.nmcli."
)
def test_dci_pipeline_real():
    rc = main(
        [
            "dci-pipeline",
            p("pipeline-real.yml"),
            "fake-cnf:ansible_extravars=ocp_component_id:%s"
            % get_ocp_component_id("OCP-4.9"),
        ]
    )
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


def helper_dci_pipeline_signal(sig):
    jobs, count = get_jobs()
    pid = os.fork()

    if pid == 0:
        os.execvp("dci-pipeline", ["dci-pipeline", "dcipipeline/pipeline-pause.yml"])
    else:
        time.sleep(10)
        os.kill(pid, sig)
        _, status = os.waitpid(pid, 0)

        assert os.WEXITSTATUS(status) == 128 + sig

        jobs2, count2 = get_jobs()
        assert count + 1 == count2
        assert jobs2[0]["status"] == "killed"


def test_dci_pipeline_sigterm():
    helper_dci_pipeline_signal(signal.SIGTERM)


def test_dci_pipeline_sigint():
    helper_dci_pipeline_signal(signal.SIGINT)


def test_dci_pipeline_error():
    rc = main(
        [
            "dci-pipeline",
            p("pipeline-error.yml"),
        ]
    )
    assert rc == 2


def test_dci_pipeline_failure():
    rc = main(
        [
            "dci-pipeline",
            p("pipeline-failure.yml"),
        ]
    )
    assert rc == 1
