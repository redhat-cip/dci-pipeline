#
# Copyright (C) 2021-2022 Red Hat, Inc.
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

import atexit
import os
import sys
import tempfile

import yaml
from test_dci_pipeline import get_jobs
from yaml.loader import SafeLoader

from dciagent.main import main as dci_main
from dciagent.main import main_s2p

TOPDIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.basename(__file__))))


def main(args):
    sys.stderr.write("+ {}\n".format(" ".join(args)))
    return dci_main(args)


def p(pname):
    return os.path.join(TOPDIR, "dciagent", "tests", "data", pname)


def test_dci_agent_ctl():
    jobs, count = get_jobs()
    os.environ["DCI_QUEUE_JOBID"] = "12"
    rc = main(
        [
            "dci-agent-ctl",
            "openshift-vanilla:components=ocp=ocp-4.8.0-0.nightly-20200703",
            p("settings.yml"),
        ]
    )
    assert rc == 0
    jobs2, count2 = get_jobs()
    assert count + 1 == count2
    assert jobs2[0]["configuration"] == "myconf"
    assert jobs2[0]["url"] == "https://lwn.net/"
    assert jobs2[0]["name"] == "openshift-vanilla"
    ocp_component = [comp for comp in jobs2[0]["components"] if comp["type"] == "ocp"]
    assert (
        len(ocp_component) == 1
        and ocp_component[0]["name"] == "ocp-4.8.0-0.nightly-20200703"
    )


def test_dci_settings2pipeline():
    pipeline = tempfile.mkstemp()[1]
    print(pipeline)
    atexit.register(lambda: os.remove(pipeline))
    rc = main_s2p(["dci-settings2pipeline", p("settings.yml"), pipeline])
    assert rc == 0
    with open(pipeline) as pipeline_fd:
        content = yaml.load(pipeline_fd, Loader=SafeLoader)
    assert content[0]["comment"] == "debugging comment"
    assert "prev_stages" not in content[0]
