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
import unittest

import yaml

import dciagent.main as main

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


class TestMain(unittest.TestCase):
    def test_main_no_args(self):
        self.assertEqual(main.main([]), 0)

    def test_process_args_simple(self):
        self.assertEqual(main.process_args(["toto", "titi"])[1:], ["toto", "titi"])

    def test_process_args_settings(self):
        args = [os.path.join(DATA_DIR, "settings.yml"), "titi"]
        processed_args = main.process_args(args)
        self.assertEqual(len(processed_args), len(args))
        self.assertRegex(processed_args[0], r"/pipeline\.yml$")

    def test_process_args(self):
        args = main.process_args(
            [
                os.path.join(DATA_DIR, "settings.yml"),
                os.path.join(DATA_DIR, "my-app-settings.yml"),
                os.path.join(DATA_DIR, "my-app-settings.yml"),
                os.path.join(DATA_DIR, "upgrade-settings.yml"),
            ]
        )
        with open(args[0]) as fd:
            pipelines = yaml.full_load(fd)
        self.assertEqual(pipelines[0]["name"], "openshift-vanilla")
        self.assertEqual(pipelines[0]["type"], "openshift")
        self.assertEqual(pipelines[0]["topic"], "OCP-4.4")
        self.assertEqual(pipelines[0]["ansible_tags"], ["working"])
        self.assertEqual(
            pipelines[0]["components"],
            [
                "ocp?name:ocp-4.4.0-0.nightly-20200701",
                "ose-tests?tags:ocp-vanilla-4.4-ok&name:ose-tests-20200628",
                "cnf-tests",
            ],
        )
        self.assertEqual(pipelines[0]["ansible_extravars"]["answer"], 42)
        self.assertEqual(
            pipelines[0]["dci_credentials"],
            os.path.abspath(
                os.path.join(DATA_DIR, "../../../rh-telco-pipeline_dci_credentials.yml")
            ),
        )
        self.assertEqual(
            pipelines[0]["ansible_inventory"],
            os.path.abspath(
                os.path.join(
                    DATA_DIR, "../../../dcipipeline/agents/openshift-vanilla/inventory"
                )
            ),
        )
        self.assertEqual(
            pipelines[0]["ansible_playbook"],
            os.path.abspath(
                os.path.join(
                    DATA_DIR, "../../../dcipipeline/agents/openshift-vanilla/agent.yml"
                )
            ),
        )
        self.assertEqual(pipelines[1]["name"], "my-app")
        self.assertEqual(pipelines[1]["type"], "openshift-app")
        self.assertEqual(pipelines[1]["topic"], "OCP-4.4")
        self.assertEqual(pipelines[1]["prev_stages"], ["openshift"])
        self.assertEqual(
            pipelines[1]["ansible_playbook"],
            "/usr/share/dci-openshift-app-agent/dci-openshift-app-agent.yml",
        )
        self.assertEqual(
            pipelines[1]["dci_credentials"], "/etc/dci/dci_credentials.yml"
        )
        self.assertEqual(pipelines[2]["prev_stages"], ["openshift"])
        self.assertEqual(pipelines[3]["type"], "openshift-upgrade")
        self.assertEqual(pipelines[3]["prev_stages"], ["openshift-app"])


if __name__ == "__main__":
    unittest.main()

# test_main.py ends here
