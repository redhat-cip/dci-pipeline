# -*- encoding: utf-8 -*-
#
# Copyright Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging
import os
import yaml


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)


def get_settings():
    settings_path = os.getenv(
        "DCI_PIPELINE_CONF", "/etc/dci-pipeline/dci_pipeline.conf"
    )
    if not os.path.exists(settings_path):
        log.error("settings file %s not found" % settings_path)
        return None
    with open(settings_path) as f:
        return yaml.load(f, Loader=yaml.SafeLoader)


def get(setting):
    settings = get_settings()
    value = os.getenv(setting)
    if value:
        return value

    if setting not in settings:
        log.error("setting %s not found" % setting)
        return None
    return settings[settings]
