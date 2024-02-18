#
# Copyright (C) 2020-2024 Red Hat, Inc.
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
    extract_build_tags,
    extract_tags,
    filter_type_tags,
    generate_and_query_clause,
    generate_query,
    generate_query_from_tags,
    get_components,
    get_config,
    get_prev_jobdefs,
    overload_dicts,
    post_process_jobdef,
    pre_process_jobdef,
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
        args = ["dci-pipeline", "jobdef:key=value"]
        result, args, _ = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [{"jobdef": {"key": "value"}}])

    def test_process_args_list(self):
        args = ["dci-pipeline", "jobdef:key=value=toto,value2"]
        result, args, _ = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [{"jobdef": {"key": ["value=toto", "value2"]}}])

    def test_process_args_dict(self):
        args = ["dci-pipeline", "jobdef:key=subkey:value", "jobdef:key=subkey2:value2"]
        result, args, _ = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(
            result,
            [
                {"jobdef": {"key": {"subkey": "value"}}},
                {"jobdef": {"key": {"subkey2": "value2"}}},
            ],
        )

    def test_process_args_dict_list(self):
        args = ["dci-pipeline", "jobdef:key=subkey:value,value2"]
        result, args, _ = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [{"jobdef": {"key": {"subkey": ["value", "value2"]}}}])

    def test_process_args_list1(self):
        args = ["dci-pipeline", "jobdef:key=value=toto,"]
        result, args, _ = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [{"jobdef": {"key": ["value=toto"]}}])

    def test_process_args_only_files(self):
        args = ["dci-pipeline", "file1", "file2"]
        result, args, _ = process_args(args)
        self.assertEqual(args, ["file1", "file2"])
        self.assertEqual(result, [])

    def test_process_args_http(self):
        args = ["dci-pipeline", "jobdef:key=http://lwn.net/"]
        result, args, _ = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [{"jobdef": {"key": "http://lwn.net/"}}])

    def test_process_args_https(self):
        args = ["dci-pipeline", "jobdef:key=https://lwn.net/"]
        result, args, _ = process_args(args)
        self.assertEqual(args, [])
        self.assertEqual(result, [{"jobdef": {"key": "https://lwn.net/"}}])

    def test_process_args_json(self):
        args = ["dci-pipeline", 'jobdef:key={"subkey":"value"}']
        result, args, _ = process_args(args)
        self.assertEqual(result, [{"jobdef": {"key": {"subkey": "value"}}}])

    def test_process_args_pipeline_name(self):
        args = ["dci-pipeline", "@pipeline:name=my-pipeline"]
        _, _, opts = process_args(args)
        self.assertEqual(opts["name"], "my-pipeline")

    def test_process_args_pipeline_id(self):
        args = ["dci-pipeline", "@pipeline:pipeline_id=my_id"]
        _, _, opts = process_args(args)
        self.assertEqual(opts["pipeline_id"], "my_id")

    @mock.patch("dcipipeline.main.usage")
    def test_process_args_pipeline_invalid_name(self, m):
        args = ["dci-pipeline", "@name:name=my-pipeline"]
        _, _, opts = process_args(args)
        self.assertTrue(m.called)

    def test_overload_dicts_add(self):
        jobdef = {"first": "value"}
        overload = {"key": ["value=toto", "value2"]}
        self.assertEqual(
            overload_dicts(overload, jobdef),
            {"first": "value", "key": ["value=toto", "value2"]},
        )

    def test_overload_dicts_replace_list(self):
        overload = {"components": ["ocp=12", "ose-tests"]}
        jobdef = {"components": ["ocp", "cnf-tests"], "topic": "OCP-4.4"}
        self.assertEqual(
            overload_dicts(overload, jobdef),
            {"components": ["ocp=12", "cnf-tests", "ose-tests"], "topic": "OCP-4.4"},
        )

    def test_overload_dicts_replace_list_search(self):
        overload = {"components": ["ocp?version:12", "ose-tests"]}
        jobdef = {"components": ["ocp", "cnf-tests"], "topic": "OCP-4.4"}
        self.assertEqual(
            overload_dicts(overload, jobdef),
            {
                "components": ["ocp?version:12", "cnf-tests", "ose-tests"],
                "topic": "OCP-4.4",
            },
        )

    def test_overload_dicts_replace_string(self):
        overload = {"components": "ocp=12"}
        jobdef = {"components": ["ocp", "cnf-tests"], "topic": "OCP-4.4"}
        self.assertEqual(
            overload_dicts(overload, jobdef),
            {"components": ["ocp=12", "cnf-tests"], "topic": "OCP-4.4"},
        )

    def test_overload_dicts_add_dict(self):
        overload = {"ansible_extravars": {"dci_comment": "universal answer"}}
        jobdef = {"ansible_extravars": {"answer": 42}}
        self.assertEqual(
            overload_dicts(overload, jobdef),
            {"ansible_extravars": {"answer": 42, "dci_comment": "universal answer"}},
        )

    def test_overload_dicts_add_list_in_dict(self):
        overload = {"ansible_extravars": {"dci_comment": "universal answer"}}
        jobdef = {"ansible_extravars": {"answer": 42}}
        self.assertEqual(
            overload_dicts(overload, jobdef),
            {"ansible_extravars": {"answer": 42, "dci_comment": "universal answer"}},
        )

    def test_jobdef_without_component(self):
        jobdef = {}
        components, jobdef = get_components("context", jobdef, "topic_id", "tag")
        self.assertEqual(jobdef, {"components": []})

    def test_prev_jobdefs(self):
        jobdef1 = {"name": "1", "type": "ocp"}
        jobdef2 = {
            "name": "2",
            "type": "ocp-upgrade",
            "prev_stages": ["ocp-upgrade", "ocp"],
        }
        jobdef3 = {
            "name": "3",
            "type": "ocp-upgrade2",
            "prev_stages": ["ocp-upgrade", "ocp"],
        }
        jobdef4 = {"name": "4", "type": "cnf2"}
        pipeline = [jobdef1, jobdef2, jobdef3, jobdef4]
        prev_jobdefs = get_prev_jobdefs(jobdef3, pipeline)
        self.assertEqual(prev_jobdefs, [jobdef2, jobdef1])

    @mock.patch("dcipipeline.main.tempfile.mkdtemp")
    def test_pre_process_jobdef(self, m):
        jobdef = {"ansible_envvars": {"envvar": "/@tmpdir"}}
        m.return_value = "/tmp/tmppath"
        jobdef_metas, jobdef = pre_process_jobdef(jobdef)
        self.assertEqual(jobdef_metas["tmpdirs"][0]["path"], "/tmp/tmppath")

    @mock.patch("dcipipeline.main.shutil.rmtree")
    @mock.patch("dcipipeline.main.upload_junit_files_from_dir")
    def test_post_process_jobdef(self, m_upload_junit, m_rmtree):
        metas = {
            "tmpdirs": [{"name": "JUNIT_OUTPUT_DIR", "path": "/tmp/junit_tmppath"}]
        }
        post_process_jobdef("context", "jobdef", metas)
        m_upload_junit.assert_called_with("context", "jobdef", "/tmp/junit_tmppath")
        m_rmtree.assert_called_with("/tmp/junit_tmppath")

        m_upload_junit.reset_mock()
        m_rmtree.reset_mock()
        metas = {"tmpdirs": [{"name": "envvar1", "path": "/tmp/tmppath"}]}
        post_process_jobdef("context", "jobdef", metas)
        self.assertTrue(not m_upload_junit.called)
        m_rmtree.assert_called_with("/tmp/tmppath")

    @mock.patch("dcipipeline.main.dci_file.create")
    def test_upload_junit_files_from_dir(self, m):
        try:
            os.makedirs("/tmp/junit-tmppath")
        except Exception:
            pass
        open("/tmp/junit-tmppath/junit-tests.xml", "a+").close()
        jobdef = {"job_info": {"job": {"id": "1"}}}
        upload_junit_files_from_dir("context", jobdef, "/tmp/junit-tmppath")
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
        config_dir, jobdefs, _ = get_config(["prog", fullpath, fullpath2])
        self.assertEqual(len(jobdefs), 1)
        self.assertEqual(
            jobdefs[0]["components"],
            [
                "storage-plugin",
                "network-plugin",
                "ocp",
                "ose-tests",
                "cnf-tests",
            ],
        )
        self.assertEqual(jobdefs[0]["ansible_extravars"], {"var": 43, "var2": 42})

    def test_extract_tags(self):
        query = "tags:build:dev,daily&version:4.11.41".split("&")
        tags, others = extract_tags(query)
        self.assertEqual(others, ["version:4.11.41"])
        self.assertEqual(tags, ["build:dev,daily"])
        build_tags, other_tags = extract_build_tags(tags)
        self.assertEqual(build_tags, ["build:dev"])
        self.assertEqual(other_tags, ["daily"])

    def test_extract_tags2(self):
        query = "tags:ocp-vanilla-4.8-ok,build:dev&version:20200628".split("&")
        tags, others = extract_tags(query)
        self.assertEqual(others, ["version:20200628"])
        self.assertEqual(tags, ["ocp-vanilla-4.8-ok,build:dev"])
        build_tags, other_tags = extract_build_tags(tags)
        self.assertEqual(build_tags, ["build:dev"])
        self.assertEqual(other_tags, ["ocp-vanilla-4.8-ok"])

    def test_filter_type_tags(self):
        self.assertEqual(filter_type_tags(["ocp?toto"], "ocp"), ["toto"])

    def test_generate_and_query_clause_simple(self):
        self.assertEqual(
            generate_and_query_clause(["status:failure"]), ",eq(status,failure)"
        )

    def test_generate_and_query_clause_multiple(self):
        self.assertEqual(
            generate_and_query_clause(["status:failure", "state:active"]),
            ",eq(status,failure),eq(state,active)",
        )

    def test_generate_and_query_clause_none(self):
        self.assertEqual(generate_and_query_clause([]), "")

    def test_generate_and_query_clause_ilike(self):
        self.assertEqual(generate_and_query_clause(["name:ocp*"]), ",ilike(name,ocp%)")

        self.assertEqual(
            generate_and_query_clause(["status:failure", "name:ocp*"]),
            ",eq(status,failure),ilike(name,ocp%)",
        )

    def test_generate_query_from_tags_empty(self):
        self.assertEqual(generate_query_from_tags([], [], "ocp"), "")

    def test_generate_query_from_tags(self):
        self.assertEqual(
            generate_query_from_tags(["ocp?ocp_tag", "other_tag"], [], "ocp"),
            ",contains(tags,ocp_tag),contains(tags,other_tag)",
        )

    def test_generate_query_from_tags_duplicate(self):
        self.assertEqual(
            generate_query_from_tags(
                ["ocp?ocp_tag", "other_tag", "build:nightly"], ["build:dev"], "ocp"
            ),
            ",contains(tags,ocp_tag),contains(tags,other_tag),or(contains(tags,build:dev),contains(tags,build:candidate),contains(tags,build:ga))",
        )

    def test_generate_query(self):
        self.assertEqual(
            generate_query("ocp", []),
            "and(eq(state,active),eq(type,ocp))",
        )

    def test_generate_query_fallback(self):
        self.assertEqual(
            generate_query("ocp", ["fallback"]),
            "and(eq(state,active),eq(type,ocp),contains(tags,fallback))",
        )


if __name__ == "__main__":
    unittest.main()

# test_main.py ends here
