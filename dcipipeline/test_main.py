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

import main


class TestMain(unittest.TestCase):

    def test_process_args_empty(self):
        args = ['dci-pipeline']
        result, args = main.process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, {})

    def test_process_args_single(self):
        args = ['dci-pipeline', 'stage:key=value']
        result, args = main.process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, {'stage': {'key': 'value'}})

    def test_process_args_list(self):
        args = ['dci-pipeline', 'stage:key=value=toto,value2']
        result, args = main.process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, {'stage': {'key': ['value=toto', 'value2']}})


if __name__ == "__main__":
    unittest.main()

# test_main.py ends here
