import os
import time

from sqlalchemy import Column, BigInteger, Integer, Boolean, String, DateTime
from sqlalchemy import func, UniqueConstraint
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.exc import NoResultFound

from akiri.framework.ext.sqlalchemy import meta

from mixin import BaseMixin, BaseDictMixin
from cache import TableauCacheManager
from util import odbc2dt, failed

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

    __table_args__ = (UniqueConstraint('envid', 'id'), 
                      UniqueConstraint('envid', 'name'))

    @classmethod
    def get(cls, envid, name, **kwargs):
        keys = {'envid':envid, 'name':name}
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
    timestamp = Column(DateTime, nullable=False)
    system_user_id = Column(Integer)
    url = Column(String)  # FIXME: make this unique.
    note = Column(String)

    # NOTE: system_user_id is not a foreign key to avoid load dependencies.

    workbook = relationship('WorkbookEntry', \
        backref=backref('updates',
                        order_by='desc(WorkbookUpdateEntry.timestamp)')
    )

    __table_args__ = (UniqueConstraint('workbookid', 'revision'),)

    # ideally: site-project-name-rev.twb
    def filename(self):
        return self.workbook.repository_url + '-rev' + self.revision + '.twb'

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
    def load(self, agent):
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

        last_created_at = self.last_created_at(envid)
        if last_created_at:
            # NOTE: the precision of the updated_at timestamp on windows
            # is greater than that on linux so this where clause often
            # returns at least one entry (if the table is non-empty)
            stmt += " WHERE created_at > '" + last_created_at + "'"

        data = agent.odbc.execute(stmt)

        updates = []
        schema = self.schema(data)

        if 'error' in data or '' not in data:
            return data

        self.server.log.debug(data)

        for row in data['']:
            wbid = row[0]
            name = row[1]
            revision = row[22]
            updated_at = odbc2dt(row[5])

            wb = WorkbookEntry.get(envid, name, default=None)
            if wb is None:
                wb = WorkbookEntry(envid=envid, id=wbid, name=name)
                session.add(wb)
            else:
                wb.id = wbid  # id is updated with each revision.

            wb.repository_url = row[2]
            wb.description = row[3]
            wb.created_at = odbc2dt(row[4])
            wb.updated_at = updated_at
            wb.owner_id = row[6]
            wb.project_id = row[7]
            wb.view_count = row[8]
            wb.size = row[9]
            wb.embedded = row[10]
            wb.thumb_user = row[11]
            wb.refreshable_extracts = row[12]
            wb.extracts_refreshed_at = odbc2dt(row[13])
            wb.lock_version = row[14]
            wb.state = row[15]
            wb.version = row[16]
            wb.checksum = row[17]
            wb.display_tabs = row[18]
            wb.data_engine_extracts = row[19]
            wb.incrementable_extracts = row[20]
            wb.site_id = row[21]
            wb.repository_data_id = row[23]
            wb.repository_extract_data_id = row[24]
            wb.first_published_at = odbc2dt(row[25])
            wb.primary_content_url = row[26]
            wb.share_description = row[27]
            wb.show_toolbar = row[28]
            wb.extracts_incremented_at = odbc2dt(row[29])
            wb.default_view_index = row[30]
            wb.luid = row[31]
            wb.asset_key_id = row[32]
            wb.document_version = row[33]

            system_user_id = users.get(wb.site_id, wb.owner_id)
            wb.system_user_id = system_user_id;

            wbu = WorkbookUpdateEntry.get(wb.workbookid, revision, default=None)
            if not wbu:
                # A new row is created each time in the Tableau database,
                # so the created_at time is actually the publish time.
                wbu = WorkbookUpdateEntry(workbookid=wb.workbookid,
                                          revision=revision,
                                          system_user_id = system_user_id,
                                          timestamp=wb.created_at,
                                          url='')
                session.add(wbu)
                updates.append(wbu)

        session.commit()

        # Second pass - build the archive files.
        for update in updates:
            filename = self.retrieve_workbook(update, agent)
            if not filename:
                self.server.log.error('Failed to retrieve workbook: %s %s',
                                      update.workbook.repository_url,
                                      update.revision)
                continue
            update.url = filename
            # retrieval is a long process, so commit after each.
            session.commit()

        return {u'status': 'OK',
                u'schema': schema,
                u'updates':str(len(updates))}

    # FIXME
    def agent_tmpdir(self, agent):
        return 'C:\\'

    # returns the filename *on the agent* or None on error.
    def build_workbook(self, update, agent, filename=None):
        if not filename: filename = update.filename()
        url = '/workbooks/' + update.workbook.repository_url + '.twb'
        dst = agent.path.join(self.agent_tmpdir(agent), filename)
        cmd = 'get %s -f "%s"' % (url, dst)
        body = self.server.tabcmd(cmd, agent)
        if failed(body):
            return None
        return dst

    # returns the filename - in self.path - or None on error.
    def retrieve_workbook(self, update, agent):
        filename = update.filename()
        path = self.build_workbook(update, agent)
        if not path:
            return None
        body = agent.filemanager.save(path, target=self.path)
        if failed(body):
            return None
        return filename

    # This is the time the last revision was created.
    # returns a UTC string or None
    def last_created_at(self, envid):
        value = WorkbookEntry.max('created_at', filters={'envid':envid})
        if value is None:
            return None
        return str(value)

