from sqlalchemy import Column, String, BigInteger, DateTime, func
from sqlalchemy.orm.exc import NoResultFound

from akiri.framework.ext.sqlalchemy import meta

from mixin import BaseMixin

class Domain(meta.Base, BaseMixin):
    __tablename__ = 'domain'

    domainid =  Column(BigInteger, unique=True, nullable=False, \
                           autoincrement=True, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)
    creation_time = Column(DateTime, server_default=func.now())
    modification_time = Column(DateTime, server_default=func.now(), \
                                   server_onupdate=func.current_timestamp())

    defaults = [{'domainid':1, 'name':'default.local'}]

    @classmethod
    def get_by_name(cls, name):
        # We expect the entry to exist, so allow a NoResultFound
        # exception to percolate up if the entry is not found.
        entry = meta.Session.query(Domain).\
            filter(Domain.name == name).one()
        return entry
