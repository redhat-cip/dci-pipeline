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

import unittest

from dcipipeline.main import process_args, overload_dicts


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


if __name__ == "__main__":
    unittest.main()

# test_main.py ends here
