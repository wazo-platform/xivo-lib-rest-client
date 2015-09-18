# -*- coding: utf-8 -*-

# Copyright (C) 2014-2015 Avencall
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import logging
import requests

from functools import partial
from requests import Session
from stevedore import extension

logger = logging.getLogger(__name__)

try:
    from requests.packages.urllib3 import disable_warnings
except ImportError:
    # XiVO Wheezy: urllib3 1.7.1 does not have warnings nor disable_warnings
    # XiVO Jessie: urllib3 1.9.1 will have warnings, use urllib3.disable_warnings()
    disable_warnings = lambda: None


class _SessionBuilder(object):

    def __init__(self,
                 host,
                 port,
                 version,
                 username,
                 password,
                 https,
                 timeout,
                 auth_method,
                 verify_certificate,
                 token):
        self.scheme = 'https' if https else 'http'
        self.host = host
        self.port = port
        self.version = version
        self.username = username
        self.password = password
        self.timeout = timeout
        self._verify_certificate = verify_certificate
        if auth_method == 'basic':
            self.auth_method = requests.auth.HTTPBasicAuth
        elif auth_method == 'digest':
            self.auth_method = requests.auth.HTTPDigestAuth
        else:
            self.auth_method = None
        self.token = token

    def session(self):
        session = Session()
        session.headers = {'Connection': 'close'}

        if self.timeout is not None:
            session.request = partial(session.request, timeout=self.timeout)
        if self.scheme == 'https':
            if not self._verify_certificate:
                disable_warnings()
                session.verify = False
            else:
                session.verify = self._verify_certificate
        if self.username and self.password:
            session.auth = self.auth_method(self.username, self.password)
        if self.token:
            session.headers['X-Auth-Token'] = self.token

        return session

    def url(self, *fragments):
        base = '{scheme}://{host}:{port}/{version}'.format(scheme=self.scheme,
                                                           host=self.host,
                                                           port=self.port,
                                                           version=self.version)
        if fragments:
            base = "{base}/{path}".format(base=base, path='/'.join(fragments))

        return base


class _Client(object):

    def __init__(self, namespace, session_builder):
        self._namespace = namespace
        self._session_builder = session_builder
        self._load_plugins()

    def _load_plugins(self):
        extension_manager = extension.ExtensionManager(self._namespace)
        try:
            extension_manager.map(self._add_command_to_client)
        except RuntimeError:
            logger.warning('No commands found')

    def _add_command_to_client(self, extension):
        command = extension.plugin(self._session_builder)
        setattr(self, extension.name, command)


def new_client_factory(ns, port, version, auth_method=None, default_https=False,
                       session_builder=_SessionBuilder):

    def new_client(host='localhost',
                   port=port,
                   version=version,
                   username=None,
                   password=None,
                   https=default_https,
                   auth_method=auth_method,
                   timeout=10,
                   verify_certificate=False,
                   token=None):
        builder = session_builder(host,
                                  port,
                                  version,
                                  username,
                                  password,
                                  https,
                                  timeout,
                                  auth_method,
                                  verify_certificate,
                                  token)
        return _Client(ns, builder)

    return new_client
