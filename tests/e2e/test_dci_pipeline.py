#
# Copyright (C) Red Hat, Inc.
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

TOPDIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.basename(__file__))))


def p(pname):
    return os.path.join(TOPDIR, "dcipipeline", pname)


def test_dci_pipeline():
    rc = main(["dci-pipeline", p("pipeline.yml")])
    assert rc == 0
    assert len(PIPELINE) == 2


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
