# Copyright (c) 2016 Intel, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""The backups V3 API."""

from oslo_log import log as logging
from webob import exc

from cinder.api.contrib import backups as backups_v2
from cinder.api import microversions as mv
from cinder.api.openstack import wsgi
from cinder.api.v3.views import backups as backup_views
from cinder import exception
from cinder.i18n import _
from cinder.policies import backups as policy


LOG = logging.getLogger(__name__)


class BackupsController(backups_v2.BackupsController):
    """The backups API controller for the OpenStack API V3."""

    _view_builder_class = backup_views.ViewBuilder

    @wsgi.Controller.api_version(mv.BACKUP_UPDATE)
    def update(self, req, id, body):
        """Update a backup."""
        context = req.environ['cinder.context']
        self.assert_valid_body(body, 'backup')
        req_version = req.api_version_request

        backup_update = body['backup']

        self.validate_name_and_description(backup_update)
        update_dict = {}
        if 'name' in backup_update:
            update_dict['display_name'] = backup_update.pop('name')
        if 'description' in backup_update:
            update_dict['display_description'] = (
                backup_update.pop('description'))
        if (req_version.matches(
                mv.BACKUP_METADATA) and 'metadata' in backup_update):
            update_dict['metadata'] = backup_update.pop('metadata')
        # Check no unsupported fields.
        if backup_update:
            msg = _("Unsupported fields %s.") % (", ".join(backup_update))
            raise exc.HTTPBadRequest(explanation=msg)

        new_backup = self.backup_api.update(context, id, update_dict)

        return self._view_builder.summary(req, new_backup)

    def _add_backup_project_attribute(self, req, backup):
        db_backup = req.get_db_backup(backup['id'])
        key = "os-backup-project-attr:project_id"
        backup[key] = db_backup['project_id']

    def show(self, req, id):
        """Return data about the given backup."""
        LOG.debug('Show backup with id %s.', id)
        context = req.environ['cinder.context']
        req_version = req.api_version_request

        # Not found exception will be handled at the wsgi level
        backup = self.backup_api.get(context, backup_id=id)
        req.cache_db_backup(backup)

        resp_backup = self._view_builder.detail(req, backup)
        if req_version.matches(mv.BACKUP_PROJECT):
            try:
                context.authorize(policy.BACKUP_ATTRIBUTES_POLICY)
                self._add_backup_project_attribute(req, resp_backup['backup'])
            except exception.PolicyNotAuthorized:
                pass
        return resp_backup

    def detail(self, req):
        resp_backup = super(BackupsController, self).detail(req)
        context = req.environ['cinder.context']
        req_version = req.api_version_request

        if req_version.matches(mv.BACKUP_PROJECT):
            try:
                context.authorize(policy.BACKUP_ATTRIBUTES_POLICY)
                for bak in resp_backup['backups']:
                    self._add_backup_project_attribute(req, bak)
            except exception.PolicyNotAuthorized:
                pass
        return resp_backup

    def _convert_sort_name(self, req_version, sort_keys):
        if req_version.matches(mv.BACKUP_SORT_NAME) and 'name' in sort_keys:
            sort_keys[sort_keys.index('name')] = 'display_name'


def create_resource():
    return wsgi.Resource(BackupsController())
