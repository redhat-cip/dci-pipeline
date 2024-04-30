#
# Copyright (C) 2023-2024 Red Hat, Inc.
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

"""
%(prog)s - Parse stdin for strings like:

Test<name>: <dci-pipeline args>

According to the configuration in the file ~/.config/dci-pipeline/auto.conf
which is an ini file with sections like:

[<name>]
cmd = dci-pipeline-check @URL -p <dci-queue>

The command takes the URL of the change (GitHub PR or Gerrit change) as argument.

Example:

$ dci-pipeline-auto https://example.com/r/c/dci-openshift-agent/+/30337 <<< <description of the change>

will launch:

dci-pipeline-check https://example.com/r/c/dci-openshift-agent/+/30337 -p <dci-queue> <dci-pipeline args>
"""

import argparse
import configparser
import os.path
import re
import shlex
import subprocess
import sys

_TEST_PIPELINE_RE = re.compile(r"Test(?P<name>\w+):\s*(?P<args>.*)")


def load_config(path):
    "load the config file"
    cfg = configparser.ConfigParser()
    cfg.read(os.path.expanduser(path))
    return cfg


def cleanup(args):
    "clean shell injection"
    return args.replace(";", "").replace("&", "").replace("|", "").strip()


def parse_description(description):
    "Extract lines like Test<name>: <dci-pipeline args>"
    ret = {}
    for line in description.splitlines():
        match = _TEST_PIPELINE_RE.match(line)
        if match:
            ret[match.group("name")] = shlex.split(cleanup(match.group("args")))
    return ret


def main(argv=sys.argv):
    """main"""
    parser = argparse.ArgumentParser(
        prog=os.path.basename(argv[0]),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("url", help="URL of the change")
    parser.add_argument(
        "infile",
        nargs="?",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="STDIN",
    )
    args = parser.parse_args(argv[1:])

    config = load_config("~/.config/dci-pipeline/auto.conf")
    pipelines = parse_description(args.infile.read())
    nb = 0
    for name, pipeline_args in pipelines.items():
        if name in config and "cmd" in config[name]:
            cmd = (
                shlex.split(config[name]["cmd"].replace("@URL", args.url))
                + pipeline_args
            )
            print(
                f"+ {' '.join(cmd)}",
                file=sys.stderr,
            )
            # avoid shell injection by using shell=False
            subprocess.check_call(cmd, shell=False)
            nb += 1
    return 0 if nb else 1


if __name__ == "__main__":
    sys.exit(main())

# auto.py ends here
