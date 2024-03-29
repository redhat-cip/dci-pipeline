#
# Copyright (C) 2023 Red Hat, Inc.
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

from dcipipeline import auto


class TestAuto(unittest.TestCase):
    def test_parse_desctription(self):
        description = "TestFoo: bar"
        self.assertEqual(auto.parse_description(description), {"Foo": ["bar"]})

    def test_cleanup(self):
        self.assertEqual(auto.cleanup("foo; bar"), "foo bar")
        self.assertEqual(auto.cleanup("foo& bar"), "foo bar")


if __name__ == "__main__":
    unittest.main()

# test_auto.py ends here
