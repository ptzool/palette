import socket

from webob import exc

from akiri.framework.api import RESTApplication
from akiri.framework.config import store

from akiri.framework.ext.sqlalchemy import meta

from controller.domain import Domain
from controller.workbooks import WorkbookEntry
from controller.util import UNDEFINED
from controller.profile import UserProfile, Role
from controller.credential import CredentialEntry

from page import PalettePage, FAKEPW
from rest import PaletteRESTHandler, required_parameters, required_role

__all__ = ["WorkbookApplication"]

class CredentialMixin(object):

    PRIMARY_KEY = 'primary'
    SECONDARY_KEY = 'secondary'

    def get_cred(self, name):
        envid = self.environment.envid
        return CredentialEntry.get_by_envid_key(envid, name, default=None)

class WorkbookApplication(PaletteRESTHandler, CredentialMixin):

    NAME = 'workbooks'

    def getuser_fromdb(self, system_users_id):
        if system_users_id < 0:
            return UNDEFINED
        user = UserProfile.get_by_system_users_id(system_users_id)
        if not user:
            return UNDEFINED
        return user.display_name()

    def getuser(self, system_users_id, cache={}):
        if system_users_id in cache:
            return cache[system_users_id]
        user = self.getuser_fromdb(system_users_id)
        cache[system_users_id] = user
        return user

    def get_cred(self, name):
        entry = super(WorkbookApplication, self).get_cred(name)
        if not entry:
            entry = CredentialEntry(envid=self.environment.envid, key=name)
            meta.Session.add(entry)
        return entry

    @required_parameters('value')
    def handle_user_POST(self, req, cred):
        value = req.POST['value']
        cred.user = value
        meta.Session.commit()
        return {'value':value}

    @required_parameters('value')
    def handle_passwd_POST(self, req, cred):
        value = req.POST['value']
        cred.setpasswd(value)
        meta.Session.commit()
        return {'value':value}

    def handle_user(self, req, key):
        cred = self.get_cred(key)
        if req.method == 'POST':
            return self.handle_user_POST(req, cred)
        value = cred and cred.user or ''
        return {'value': value}
        
    def handle_passwd(self, req, key):
        cred = self.get_cred(key)
        if req.method == 'POST':
            return self.handle_passwd_POST(req, cred)
        value = cred and FAKEPW or ''
        return {'value': value}

    def handle_get(self, req):
        users = {}
        envid = self.environment.envid

        workbooks = []
        for entry in WorkbookEntry.get_all_by_envid(envid):
            data = entry.todict(pretty=True)

            updates = []
            for update in entry.updates:
                d = update.todict(pretty=True)
                d['username'] = self.getuser(update.system_users_id, users)
                updates.append(d)
            data['updates'] = updates

            if entry.updates:
                # The summary field contains the name of the current owner,
                # which can be found from the last (by-time) update entry.
                system_users_id = entry.updates[0].system_users_id
                data['summary'] = self.getuser(system_users_id, users)

            workbooks.append(data)

        return {'workbooks': workbooks}

    @required_role(Role.MANAGER_ADMIN)
    def handle(self, req):
        path_info = self.base_path_info(req)
        if path_info == 'primary/user':
            return self.handle_user(req, key=self.PRIMARY_KEY)
        elif path_info == 'primary/password':
            return self.handle_passwd(req, key=self.PRIMARY_KEY)
        elif path_info == 'secondary/user':
            return self.handle_user(req, key=self.SECONDARY_KEY)
        elif path_info == 'secondary/password':
            return self.handle_passwd(req, key=self.SECONDARY_KEY)
        elif path_info:
            raise exc.HTTPBadRequest()

        if req.method == "GET":
            return self.handle_get(req)
        else:
            raise exc.HTTPBadRequest()


class TabcmdPage(PalettePage, CredentialMixin):
    TEMPLATE = "tabcmd.mako"
    active = 'tabcmd'
    expanded = True
    required_role = Role.MANAGER_ADMIN

    def render(self, req, obj=None):
        primary = self.get_cred(self.PRIMARY_KEY)
        if primary:
            req.primary_user = primary.user
            req.primary_pw = primary.embedded and FAKEPW or ''
        else:
            req.primary_user = req.primary_pw = ''
        secondary = self.get_cred(self.SECONDARY_KEY)
        if secondary:
            req.secondary_user = secondary.user
            req.secondary_pw = secondary.embedded and FAKEPW or ''
        else:
            req.secondary_user = req.secondary_pw = ''
        return super(TabcmdPage, self).render(req, obj=obj)

def make_tabcmd(global_conf):
    return TabcmdPage(global_conf)
