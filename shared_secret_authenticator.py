# -*- coding: utf-8 -*-
#
# Shared Secret Authenticator module for Matrix Synapse
# Copyright (C) 2018 Slavi Pantaleev
#
# http://devture.com/
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# KMJ 2020-05-27 added config parameter allowed-user (multi)

import logging
import hashlib
import hmac
import re
from twisted.internet import defer

logger = logging.getLogger(__name__)

class SharedSecretAuthenticator(object):

    def __init__(self, config, account_handler):
        self.account_handler = account_handler
        self.sharedSecret = config['sharedSecret']
        self.sharedWhitelist = config['sharedWhitelist']

        # lets avoid logger error for missing request
        # errors can be solved by adding filters to the logger to
        #     shared_secret_authenticator:
        #       level: DEBUG
        #       filters: [context]
        #
        logger.info('Whitelisted user: %s', self.sharedWhitelist)

    @defer.inlineCallbacks
    def check_password(self, user_id, password):
        # The password is supposed to be an HMAC of the user id, keyed with the shared secret.
        # It's not really a password in this case.
        given_hmac = password.encode('utf-8')

        logger.info('Authenticating user: %s', user_id)

        h = hmac.new(self.sharedSecret.encode('utf-8'), user_id.encode('utf-8'), hashlib.sha512)
        computed_hmac = h.hexdigest().encode('utf-8')

        try:
            is_identical = hmac.compare_digest(computed_hmac, given_hmac)
        except AttributeError:
            # `hmac.compare_digest` is only available on Python >= 2.7.7
            # Fall back to being somewhat insecure on older versions.
            is_identical = (computed_hmac == given_hmac)

        if not is_identical:
            logger.info('Bad hmac value for user: %s', user_id)
            defer.returnValue(False)
            return

        # this could be handled better ihmo, suggestions welcome
        # if not whitelisted deny shared secret based logins

        user_is_ok = ''
        is_ok_to_auth = ''
        for ok_users in self.sharedWhitelist:
            logger.info('checking user %s for whitelisting against %s', user_id, ok_users)
            user_is_ok = re.match(user_id, ok_users)
            if user_is_ok:
                logger.info('IS OK: %s', user_id)
                is_ok_to_auth = user_id
            else:
                logger.info('IS NOT OK: %s', user_id)

        if not is_ok_to_auth:
            logger.info('user not allowed to login: %s', user_id)
            defer.returnValue(False)
            return

        if not (yield self.account_handler.check_user_exists(user_id)):
            logger.info('Refusing to authenticate missing user: %s', user_id)
            defer.returnValue(False)
            return

        logger.info('Authenticated user: %s', user_id)
        defer.returnValue(True)

    @staticmethod
    def parse_config(config):

        # Note parse_config() is already checked during the call to load_module
        # we should not do anything here

        if 'sharedWhitelist' not in config:
            raise Exception('Missing sharedWhitelist parameter for SharedSecretAuthenticator')

        if 'sharedSecret' not in config:
            raise Exception('Missing sharedSecret parameter for SharedSecretAuthenticator')

        return config
