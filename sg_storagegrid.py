#/bin/python3
# -*- coding: utf-8 -*-
# Author: Sudeesh Varier
# Date: 2024-01-08
# Version: 1.0

import logging
import requests
import json
import functools
import time
from optparse import OptionParser

class StorageGridUtils:
    def __init__(self, hostname, log_file, debug=False):
        self.HOSTNAME = hostname
        self.LOG_FILE = log_file
        self.debug = debug
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(logging.StreamHandler())
        self.logger.addHandler(logging.FileHandler(self.LOG_FILE))
        self.logger.info("Logging initialized")

    def url_creator(self, url: str = None):
        url_prefix = 'https://'
        url_tail_apiversion = '/api/v4'
        base_url = url_prefix + self.HOSTNAME + url_tail_apiversion
        if url is None:
            return base_url
        else:
            return base_url + url

    def get_token(self, payload: dict, s3account_name: str = None):
        auth_url = self.url_creator('/authorize')
        auth_response = requests.post(auth_url, data=json.dumps(payload), headers={'Content-Type': 'application/json'}, verify=False)
        if auth_response.status_code == 200:
            if s3account_name is not None:
                self.logger.info(f"Token received for account {s3account_name}")
                return json.loads(auth_response.text)['data']
            else:
                self.logger.info("Token received for grid authentication")
                return json.loads(auth_response.text)['data']
        else:
            if s3account_name is not None:
                self.logger.error(f"Failed to get token for account {s3account_name}")
            else:
                self.logger.error("Failed to get token for grid authentication")
            return None