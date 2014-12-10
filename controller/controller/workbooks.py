import os

from sqlalchemy import Column, BigInteger, Integer, Boolean, String, DateTime
from sqlalchemy import UniqueConstraint
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relationship, backref

# pylint: disable=import-error,no-name-in-module
from akiri.framework.ext.sqlalchemy import meta
# pylint: enable=import-error,no-name-in-module

from mixin import BaseMixin, BaseDictMixin
from cache import TableauCacheManager #FIXME
from manager import synchronized
from util import failed, success
from odbc import ODBC

from diskcheck import DiskCheck, DiskException
from event_control import EventControl
from place_file import PlaceFile
from files import FileManager

from sites import Site
from projects import Project

# NOTE: system_user_id is maintained in two places.  This is not ideal from
# a db design perspective but makes the find-by-current-owner code clearer.
class WorkbookEntry(meta.Base, BaseMixin, BaseDictMixin):
    __tablename__ = "workbooks"

    workbookid = Column(BigInteger, unique=True, nullable=False,
                        autoincrement=True, primary_key=True)
    envid = Column(BigInteger, ForeignKey("environment.envid"), nullable=False)
    system_user_id = Column(Integer)
    id = Column(BigInteger, nullable=False)
    name = Column(String)
    repository_url = Column(String)
    description = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    owner_id = Column(Integer)
    project_id = Column(Integer)
    view_count = Column(Integer)
    size = Column(BigInteger)
    embedded = Column(String)
    thumb_user = Column(String)
    refreshable_extracts = Column(Boolean)
    extracts_refreshed_at = Column(DateTime)
    lock_version = Column(Integer)
    state = Column(String)
    version = Column(String)
    checksum = Column(String)
    display_tabs = Column(Boolean)
    data_engine_extracts = Column(Boolean)
    incrementable_extracts = Column(Boolean)
    site_id = Column(Integer)
    repository_data_id = Column(BigInteger)
    repository_extract_data_id = Column(BigInteger)
    first_published_at = Column(DateTime)
    primary_content_url = Column(String)
    share_description = Column(String)
    show_toolbar = Column(Boolean)
    extracts_incremented_at = Column(DateTime)
    default_view_index = Column(Integer)
    luid = Column(String)
    assert_key_id = Column(Integer)
    document_version = Column(String)

    __table_args__ = (UniqueConstraint('envid', 'id'),)

    def __getattr__(self, name):
        if name == 'site':
            return Site.get_name_by_id(self.envid, self.site_id)
        elif name == 'project':
            return Project.get_name_by_id(self.envid, self.project_id)
        raise AttributeError(name)

    def fileext(self):
        if self.data_engine_extracts:
            return 'twbx'
        return 'twb'

    @classmethod
    def get(cls, envid, name, site_id, project_id, **kwargs):
        keys = {'envid':envid, 'name':name,
                'site_id':site_id, 'project_id':project_id}
        return cls.get_unique_by_keys(keys, **kwargs)

    @classmethod
    def get_by_url(cls, envid, url, **kwargs):
        # technically the Tableau database does not guarantee uniqueness.
        keys = {'envid':envid, 'repository_url': url}
        return cls.get_unique_by_keys(keys, **kwargs)

    @classmethod
    def get_all_by_envid(cls, envid):
        return cls.get_all_by_keys({'envid':envid}, order_by='name')

    @classmethod
    def get_all_by_system_user(cls, envid, system_user_id):
        filters = {'envid':envid, 'system_user_id':system_user_id}
        return cls.get_all_by_keys(filters, order_by='name')


class WorkbookUpdateEntry(meta.Base, BaseMixin, BaseDictMixin):
    __tablename__ = "workbook_updates"

    wuid = Column(BigInteger, unique=True, nullable=False, \
                  autoincrement=True, primary_key=True)
    workbookid = Column(BigInteger, ForeignKey("workbooks.workbookid"))
    revision = Column(String, nullable=False)
    fileid = Column(Integer, ForeignKey("files.fileid"))
    timestamp = Column(DateTime, nullable=False)
    system_user_id = Column(Integer)
    url = Column(String)  # FIXME: make this unique.
    note = Column(String)

    # NOTE: system_user_id is not a foreign key to avoid load dependencies.

    workbook = relationship('WorkbookEntry', \
        backref=backref('updates',
                        order_by='desc(WorkbookUpdateEntry.revision)')
    )

    __table_args__ = (UniqueConstraint('workbookid', 'revision'),)

    # ideally: site-project-name-rev.twb
    def basename(self):
        # pylint: disable=no-member
        site = self.workbook.site
        if not site:
            site = self.workbook.site_id
        project = self.workbook.project
        if not project:
            project = self.workbook.project_id
        filename = site + '-' + project + '-'
        filename += self.workbook.repository_url + '-rev' + self.revision
        return filename.replace(' ', '_')

    @classmethod
    def get(cls, wbid, revision, **kwargs):
        return cls.get_unique_by_keys({'workbookid': wbid,
                                       'revision': revision},
                                      **kwargs)

    @classmethod
    def get_by_id(cls, wuid, **kwargs):
        return cls.get_unique_by_keys({'wuid': wuid}, **kwargs)

    @classmethod
    def get_by_url(cls, url, **kwargs):
        return cls.get_unique_by_keys({'url': url}, **kwargs)


class WorkbookManager(TableauCacheManager):

    def __init__(self, server):
        super(WorkbookManager, self).__init__(server)
        path = server.config.get('palette', 'workbook_archive_dir')
        self.path = os.path.abspath(path)

    # really sync *and* load
    @synchronized('workbooks')
    def load(self, agent):
        # pylint: disable=too-many-locals
        if not self._cred_check():
            return {u'error': 'Can not load workbooks: missing credentials.'}

        envid = self.server.environment.envid
        users = self.load_users(agent)

        stmt = \
            'SELECT id, name, repository_url, description,' +\
            ' created_at, updated_at, owner_id, project_id,' +\
            ' view_count, size, embedded, thumb_user,' +\
            ' refreshable_extracts, extracts_refreshed_at, lock_version,' +\
            ' state, version, checksum, display_tabs, data_engine_extracts,' +\
            ' incrementable_extracts, site_id, revision,' +\
            ' repository_data_id, repository_extract_data_id,' +\
            ' first_published_at, primary_content_url, share_description,' +\
            ' show_toolbar, extracts_incremented_at, default_view_index,' +\
            ' luid, asset_key_id, document_version ' +\
            'FROM workbooks'

        session = meta.Session()

        last_created_at = self._last_created_at(envid)
        if last_created_at:
            stmt += " WHERE created_at > '" + last_created_at + "'"

        data = agent.odbc.execute(stmt)

        updates = []

        if 'error' in data or '' not in data:
            self.log.debug("workbooks load: bad data: %s", str(data))
            return data

        self.log.debug(data)

        for odbcdata in ODBC.load(data):
            name = odbcdata.data['name']
            revision = odbcdata.data['revision']
            site_id = odbcdata.data['site_id']
            project_id = odbcdata.data['project_id']

            wbe = WorkbookEntry.get(envid, name, site_id, project_id,
                                    default=None)
            if wbe is None:
                wbe = WorkbookEntry(envid=envid, name=name,
                                    site_id=site_id, project_id=project_id)
                session.add(wbe)

            # NOTE: id is updated with each revision.
            odbcdata.copyto(wbe, excludes=['revision'])

            system_user_id = users.get(wbe.site_id, wbe.owner_id)
            wbe.system_user_id = system_user_id

            # must commit here so that update foreign keys work.
            session.commit()

            wbu = WorkbookUpdateEntry.get(wbe.workbookid,
                                          revision,
                                          default=None)
            if not wbu:
                # A new row is created each time in the Tableau database,
                # so the created_at time is actually the publish time.
                wbu = WorkbookUpdateEntry(workbookid=wbe.workbookid,
                                          revision=revision,
                                          system_user_id=system_user_id,
                                          timestamp=wbe.created_at,
                                          url='')
                session.add(wbu)
                updates.append(wbu)

            self.log.debug("workbook update '%s', revision %s", name, revision)

        session.commit()

        # Second pass - build the archive files.
        for update in updates:
            session.refresh(update)
            self._archive_twb(agent, update)

        return {u'status': 'OK',
                u'schema': self.schema(data),
                u'updates': len(updates)}


    @synchronized('workbook.fixup')
    def fixup(self, agent):

        connection = meta.engine.connect()

        stmt = \
            "SELECT wuid FROM workbook_updates " +\
            "WHERE ((workbookid, revision) IN " +\
            "  (SELECT workbookid, revision FROM workbooks)) AND " +\
            "    ((url = '') OR (url IS NULL))"

        ids = [x['wuid'] for x in connection.execute(stmt)]
        self.log.debug('workbook fixup : ' + str(ids))
        connection.close()

        session = meta.Session()

        if ids:
            # potentially serveral thousand?
            updates = session.query(WorkbookUpdateEntry).\
                      filter(WorkbookUpdateEntry.wuid.in_(ids)).all()

            for update in updates:
                self._archive_twb(agent, update)
            count = len(updates)
        else:
            count = 0

        return {u'status': 'OK',
                u'updates': count}

    # returns the filename *on the agent* or None on error.
    def _build_twb(self, agent, update):
        try:
            # fixme: Specify a minimum disk space required other than 0?
            dcheck = DiskCheck(self.server, agent, self.server.WORKBOOKS_DIR,
                               FileManager.FILE_TYPE_WORKBOOK, 0)
        except DiskException, ex:
            self._eventgen(update, "build_workbook disk check : " + str(ex))
            return None

        tmpdir = dcheck.primary_dir
        ext = update.workbook.fileext()

        dst = self._tabcmd_get(agent, update, tmpdir, ext)
        if dst is None:
            # _tabcmd_get generates an event on failure.
            return None
        if ext == 'twbx':
            dst = self._extract_twb_from_twbx(agent, update, dst)
            if not dst:
                # _extract_twb_from_twbx generates an event on failure.
                return None

        # move twbx/twb to resting location.
        file_size = 0
        try:
            file_size_body = agent.filemanager.filesize(dst)
        except IOError as ex:
            self.log.error("build_workbook: filemanager.filesize('%s')" +
                           "failed: %s", dst, str(ex))
        else:
            if not success(file_size_body):
                self.log.error("build_workbook: Failed to get size of " + \
                               "workbook file %s: %s", dst,
                               file_size_body['error'])
            else:
                file_size = file_size_body['size']

        auto = True
        place = PlaceFile(self.server, agent, dcheck, dst, file_size, auto,
                          enable_delete=False)
        self.log.debug("build_workbook: %s", place.info)
        # Remember the fileid
        update.fileid = place.placed_file_entry.fileid
        return dst

    # returns the filename or None on error.
    def _retrieve_twb(self, agent, update):
        path = self._build_twb(agent, update)
        if not path:
            # build_workbook prints errors and calls _eventgen().
            return None
        self.log.debug('Retrieving workbook: %s', path)
        try:
            body = agent.filemanager.save(path, target=self.path)
        except IOError as ex:
            self.log.debug("Error saving workbook '%s': %s", path, str(ex))
            return None

        if failed(body):
            self._eventgen(self, update, data=body)
            return None
        else:
            self.log.debug('Retrieved workbook: %s', path)
        try:
            agent.filemanager.delete(path)
        except IOError as ex:
            self.log.debug("Error deleting workbook twb '%s': %s",
                            path, str(ex))
            return None

        return agent.path.basename(path)

    # Retrieve the twb file of an update and set the url.
    def _archive_twb(self, agent, update):
        filename = self._retrieve_twb(agent, update)
        if not filename:
            self.log.error('Failed to retrieve twb: %s %s',
                           update.workbook.repository_url, update.revision)
            return
        update.url = filename
        self.log.debug("workbooks load: update.url: %s", filename)

        # retrieval is a long process, so commit after each.
        meta.Session.commit()

    # This is the time the last revision was created - each revision is a new
    # row, so created_at works (instead of updated_at).
    # returns a UTC string or None
    def _last_created_at(self, envid):
        value = WorkbookEntry.max('created_at', filters={'envid':envid})
        if value is None:
            return None
        return str(value)

    # See if credentials exist.
    def _cred_check(self):
        """Returns None if there are credentials and Non-None/False
           if there are credentials."""

        cred = self.server.cred.get('primary', default=None)
        if not cred:
            cred = self.server.cred.get('secondary', default=None)

        if cred:
            if not cred.user:
                cred = None

        return cred

    # Run 'tabcmd get' on the agent to retrieve the twb/twbx file
    # then return its path or None in the case of an error.
    def _tabcmd_get(self, agent, update, tmpdir, ext):
        url = '/workbooks/' + update.workbook.repository_url + '.' + ext
        dst = agent.path.join(tmpdir, update.basename() + '.' + ext)
        cmd = 'get %s -f "%s"' % (url, dst)

        self.log.debug('building workbook archive: ' + dst)

        for _ in range(3):
            body = self.server.tabcmd(cmd, agent)
            if failed(body):
                if 'stderr' in body and 'Service Unavailable' in body['stderr']:
                    # 503 error, retry
                    self.log.debug(cmd + ' : 503 Service Unavailable, retrying')
                    continue
                break
            else:
                return dst
        self._eventgen(update, data=body)
        return None

    # A twbx file is just a zipped twb + associated tde files.
    # Extract the twb and return the path.
    def _extract_twb_from_twbx(self, agent, update, dst):
        cmd = 'ptwbx ' + '"' + dst + '"'
        body = self.server.cli_cmd(cmd, agent, timeout=60*30)
        if failed(body):
            self._eventgen(update, data=body)
            try:
                agent.filemanager.delete(dst)
            except IOError as ex:
                self.log.debug("Error deleting workbook dst '%s': %s",
                                dst, str(ex))
            return None
        dst = dst[0:-1] # drop the trailing 'x' from the file extension.
        return dst

    # Generate an event in case of a failure.
    def _eventgen(self, update, error=None, data=None):
        key = EventControl.WORKBOOK_ARCHIVE_FAILED
        if data is None:
            data = {}
        data = dict(update.workbook.todict().items() + \
                    update.todict().items() + \
                    data.items())
        if 'embedded' in data:
            del data['embedded']
        if error:
            self.log.error(error)
            data['error'] = error
        return self.server.event_control.gen(key, data)
