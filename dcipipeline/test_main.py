#
# Copyright (C) 2020 Red Hat, Inc.
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

import mock
import unittest
import os

from dcipipeline.main import (
    process_args,
    overload_dicts,
    get_prev_stages,
    pre_process_stage,
    post_process_stage,
)


class TestMain(unittest.TestCase):
    def test_process_args_empty(self):
        args = ["dci-pipeline"]
        result, args = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [])

    def test_process_args_single(self):
        args = ["dci-pipeline", "stage:key=value"]
        result, args = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [{"stage": {"key": "value"}}])

    def test_process_args_list(self):
        args = ["dci-pipeline", "stage:key=value=toto,value2"]
        result, args = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [{"stage": {"key": ["value=toto", "value2"]}}])

    def test_process_args_dict(self):
        args = ["dci-pipeline", "stage:key=subkey:value", "stage:key=subkey2:value2"]
        result, args = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(
            result,
            [
                {"stage": {"key": {"subkey": "value"}}},
                {"stage": {"key": {"subkey2": "value2"}}},
            ],
        )

    def test_process_args_dict_list(self):
        args = ["dci-pipeline", "stage:key=subkey:value,value2"]
        result, args = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [{"stage": {"key": {"subkey": ["value", "value2"]}}}])

    def test_process_args_list1(self):
        args = ["dci-pipeline", "stage:key=value=toto,"]
        result, args = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [{"stage": {"key": ["value=toto"]}}])

    def test_process_args_only_files(self):
        args = ["dci-pipeline", "file1", "file2"]
        result, args = process_args(args)
        self.assertEqual(args, ["file1", "file2"])
        self.assertEqual(result, [])

    def test_process_args_http(self):
        args = ["dci-pipeline", "stage:key=http://lwn.net/"]
        result, args = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [{"stage": {"key": "http://lwn.net/"}}])

    def test_process_args_https(self):
        args = ["dci-pipeline", "stage:key=https://lwn.net/"]
        result, args = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [{"stage": {"key": "https://lwn.net/"}}])

    def test_overload_dicts_add(self):
        stage = {"first": "value"}
        overload = {"key": ["value=toto", "value2"]}
        self.assertEqual(
            overload_dicts(overload, stage),
            {"first": "value", "key": ["value=toto", "value2"]},
        )

    def test_overload_dicts_replace_list(self):
        overload = {"components": ["ocp=12", "ose-tests"]}
        stage = {"components": ["ocp", "cnf-tests"], "topic": "OCP-4.4"}
        self.assertEqual(
            overload_dicts(overload, stage),
            {"components": ["ocp=12", "cnf-tests", "ose-tests"], "topic": "OCP-4.4"},
        )

    def test_overload_dicts_add_dict(self):
        overload = {"ansible_extravars": {"dci_comment": "universal answer"}}
        stage = {"ansible_extravars": {"answer": 42}}
        self.assertEqual(
            overload_dicts(overload, stage),
            {"ansible_extravars": {"answer": 42, "dci_comment": "universal answer"}},
        )

    def test_overload_dicts_add_list_in_dict(self):
        overload = {"ansible_extravars": {"dci_comment": "universal answer"}}
        stage = {"ansible_extravars": {"answer": 42}}
        self.assertEqual(
            overload_dicts(overload, stage),
            {"ansible_extravars": {"answer": 42, "dci_comment": "universal answer"}},
        )

    def test_prev_stages(self):
        stage1 = {"name": "1", "type": "ocp"}
        stage2 = {
            "name": "2",
            "type": "ocp-upgrade",
            "prev_stages": ["ocp-upgrade", "ocp"],
        }
        stage3 = {
            "name": "3",
            "type": "ocp-upgrade2",
            "prev_stages": ["ocp-upgrade", "ocp"],
        }
        stage4 = {"name": "4", "type": "cnf2"}
        pipeline = [stage1, stage2, stage3, stage4]
        prev_stages = get_prev_stages(stage3, pipeline)
        self.assertEqual(prev_stages, [stage2, stage1])

    @mock.patch("dcipipeline.main.tempfile.mkdtemp")
    def test_pre_process_stage(self, m):
        stage = {"ansible_envvars": {"envvar": "/@tmpdir"}}
        m.return_value = "/tmp/tmppath"
        stage_metas, stage = pre_process_stage(stage)
        self.assertEqual(stage_metas["tmpdirs"][0], "/tmp/tmppath")

    @mock.patch("dcipipeline.main.dci_file.create")
    def test_post_process_stage(self, m):
        os.makedirs("/tmp/tmppath/")
        f = open("/tmp/tmppath/fake.xml", "a+")
        metas = {"tmpdirs": ["/tmp/tmppath"]}
        stage = {"job_info": {"job": {"id": "1"}}}
        context = {"job": {"id": "1"}}
        f.close()
        post_process_stage(context, stage, metas)
        m.assert_called_with(
            context,
            "junit_fake.xml",
            file_path="/tmp/tmppath/fake.xml",
            mime="application/junit",
            job_id="1")


if __name__ == "__main__":
    unittest.main()

# test_main.py ends here
