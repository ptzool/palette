from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy import Integer, BigInteger, SmallInteger
from sqlalchemy import not_, UniqueConstraint
from sqlalchemy.schema import ForeignKey

import akiri.framework.sqlalchemy as meta

from mixin import BaseMixin

class Site(meta.Base, BaseMixin):
    #pylint: disable=too-many-instance-attributes
    __tablename__ = 'sites'

    # FIXME: BigInteger
    siteid = Column(BigInteger, primary_key=True)
    envid = Column(Integer, ForeignKey("environment.envid"), primary_key=True)
    id = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    url_namespace = Column(String)
    status = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    user_quota = Column(Integer)
    content_admin_mode = Column(Integer)
    storage_quota = Column(BigInteger)
    metrics_level = Column(SmallInteger)
    status_reason = Column(String)
    subscriptions_enabled = Column(Boolean, nullable=False)
    custom_subscription_footer = Column(String)
    custom_subscription_email = Column(String)
    luid = Column(String, unique=True)
    query_limit = Column(Integer)

    __table_args__ = (UniqueConstraint('envid', 'id'),)

    @classmethod
    def get(cls, envid, tid, **kwargs):
        keys = {'envid':envid, 'id':tid}
        return cls.get_unique_by_keys(keys, **kwargs)

    @classmethod
    def get_name_by_id(cls, envid, tid):
        entry = cls.get(envid, tid, default=None)
        if entry is None:
            return None
        return entry.name

    @classmethod
    def all(cls, envid):
        return cls.get_all_by_keys({'envid':envid}, order_by='name')

    @classmethod
    def sync(cls, agent):
        envid = agent.server.environment.envid
        stmt = \
            'SELECT id, name, status, created_at, updated_at, ' +\
            'user_quota, content_admin_mode, storage_quota, metrics_level, '+\
            'status_reason, subscriptions_enabled, ' +\
            'custom_subscription_footer, custom_subscription_email, '+\
            'luid, query_limit, url_namespace ' +\
            'FROM sites'

        data = agent.odbc.execute(stmt)
        if 'error' in data:
            return data
        if '' not in data:
            data['error'] = "Missing '' key in query response."
            return data

        ids = []

        session = meta.Session()
        for row in data['']:
            entry = Site.get(envid, row[0], default=None)
            if not entry:
                entry = Site(envid=envid, id=row[0])
                session.add(entry)
            entry.name = row[1]
            entry.status = row[2]
            entry.created_at = row[3]
            entry.updated_at = row[4]
            entry.user_quota = row[5]
            entry.content_admin_mode = row[6]
            entry.storage_quota = row[7]
            entry.metrics_level = row[8]
            entry.status_reason = row[9]
            entry.subscriptions_enabled = row[10]
            entry.custom_subscription_footer = row[11]
            entry.custom_subscription_email = row[12]
            entry.luid = row[13]
            entry.query_limit = row[14]
            entry.url_namespace = row[15]
            ids.append(entry.siteid)

        # FIXME: don't delete
        session.query(Site).\
            filter(not_(Site.siteid.in_(ids))).\
            delete(synchronize_session='fetch')

        session.commit()

        d = {u'status': 'OK', u'count': len(data[''])}
        return d

    @classmethod
    def cache(cls, envid):
        return cls.cache_by_key(envid, key='id')

