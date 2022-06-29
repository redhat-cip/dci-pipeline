#
# Copyright (C) 2020-2022 Red Hat, Inc.
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

import mock

from dcipipeline.main import (
    get_components,
    get_config,
    get_prev_stages,
    overload_dicts,
    post_process_stage,
    pre_process_stage,
    process_args,
    upload_junit_files_from_dir,
)


class TestMain(unittest.TestCase):
    def test_process_args_empty(self):
        args = ["dci-pipeline"]
        result, args, opts = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [])
        self.assertEqual(opts["name"], "pipeline")

    def test_process_args_single(self):
        args = ["dci-pipeline", "stage:key=value"]
        result, args, _ = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [{"stage": {"key": "value"}}])

    def test_process_args_list(self):
        args = ["dci-pipeline", "stage:key=value=toto,value2"]
        result, args, _ = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [{"stage": {"key": ["value=toto", "value2"]}}])

    def test_process_args_dict(self):
        args = ["dci-pipeline", "stage:key=subkey:value", "stage:key=subkey2:value2"]
        result, args, _ = process_args(args)
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
        result, args, _ = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [{"stage": {"key": {"subkey": ["value", "value2"]}}}])

    def test_process_args_list1(self):
        args = ["dci-pipeline", "stage:key=value=toto,"]
        result, args, _ = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [{"stage": {"key": ["value=toto"]}}])

    def test_process_args_only_files(self):
        args = ["dci-pipeline", "file1", "file2"]
        result, args, _ = process_args(args)
        self.assertEqual(args, ["file1", "file2"])
        self.assertEqual(result, [])

    def test_process_args_http(self):
        args = ["dci-pipeline", "stage:key=http://lwn.net/"]
        result, args, _ = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [{"stage": {"key": "http://lwn.net/"}}])

    def test_process_args_https(self):
        args = ["dci-pipeline", "stage:key=https://lwn.net/"]
        result, args, _ = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [{"stage": {"key": "https://lwn.net/"}}])

    def test_process_args_pipeline_name(self):
        args = ["dci-pipeline", "@pipeline:name=my-pipeline"]
        _, _, opts = process_args(args)
        self.assertEqual(opts["name"], "my-pipeline")

    @mock.patch("dcipipeline.main.usage")
    def test_process_args_pipeline_invalid_name(self, m):
        args = ["dci-pipeline", "@name:name=my-pipeline"]
        _, _, opts = process_args(args)
        self.assertTrue(m.called)

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

    def test_overload_dicts_replace_list_search(self):
        overload = {"components": ["ocp?name:12", "ose-tests"]}
        stage = {"components": ["ocp", "cnf-tests"], "topic": "OCP-4.4"}
        self.assertEqual(
            overload_dicts(overload, stage),
            {
                "components": ["ocp?name:12", "cnf-tests", "ose-tests"],
                "topic": "OCP-4.4",
            },
        )

    def test_overload_dicts_replace_string(self):
        overload = {"components": "ocp=12"}
        stage = {"components": ["ocp", "cnf-tests"], "topic": "OCP-4.4"}
        self.assertEqual(
            overload_dicts(overload, stage),
            {"components": ["ocp=12", "cnf-tests"], "topic": "OCP-4.4"},
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

    def test_stage_without_component(self):
        stage = {}
        components, stage = get_components("context", stage, "topic_id", "tag")
        self.assertEqual(stage, {"components": []})

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
        self.assertEqual(stage_metas["tmpdirs"][0]["path"], "/tmp/tmppath")

    @mock.patch("dcipipeline.main.shutil.rmtree")
    @mock.patch("dcipipeline.main.upload_junit_files_from_dir")
    def test_post_process_stage(self, m_upload_junit, m_rmtree):
        metas = {
            "tmpdirs": [{"name": "JUNIT_OUTPUT_DIR", "path": "/tmp/junit_tmppath"}]
        }
        post_process_stage("context", "stage", metas)
        m_upload_junit.assert_called_with("context", "stage", "/tmp/junit_tmppath")
        m_rmtree.assert_called_with("/tmp/junit_tmppath")

        m_upload_junit.reset_mock()
        m_rmtree.reset_mock()
        metas = {"tmpdirs": [{"name": "envvar1", "path": "/tmp/tmppath"}]}
        post_process_stage("context", "stage", metas)
        self.assertTrue(not m_upload_junit.called)
        m_rmtree.assert_called_with("/tmp/tmppath")

    @mock.patch("dcipipeline.main.dci_file.create")
    def test_upload_junit_files_from_dir(self, m):
        try:
            os.makedirs("/tmp/junit-tmppath")
        except Exception:
            pass
        open("/tmp/junit-tmppath/junit-tests.xml", "a+").close()
        stage = {"job_info": {"job": {"id": "1"}}}
        upload_junit_files_from_dir("context", stage, "/tmp/junit-tmppath")
        m.assert_called_with(
            "context",
            "junit-tests",
            file_path="/tmp/junit-tmppath/junit-tests.xml",
            mime="application/junit",
            job_id="1",
        )

    def test_get_config(self):
        basedir = os.path.dirname(__file__)
        fullpath = os.path.join(basedir, "comp.yml")
        fullpath2 = os.path.join(basedir, "comp2.yml")
        config_dir, stages, _ = get_config(["prog", fullpath, fullpath2])
        self.assertEqual(len(stages), 1)
        self.assertEqual(
            stages[0]["components"],
            [
                "storage-plugin",
                "network-plugin",
                "ocp",
                "ose-tests",
                "cnf-tests",
            ],
        )
        self.assertEqual(stages[0]["ansible_extravars"], {"var": 43, "var2": 42})


if __name__ == "__main__":
    unittest.main()

# test_main.py ends here
