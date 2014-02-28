import sqlalchemy
from sqlalchemy import Column, String, BigInteger, DateTime, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound

import meta

class DomainEntry(meta.Base):
    __tablename__ = 'domain'

    domainid =  Column(BigInteger, unique=True, nullable=False, \
      autoincrement=True, primary_key=True)
    domainname = Column(String, unique=True, nullable=False, \
      index=True)
    creation_time = Column(DateTime, server_default=func.now())
    modification_time = Column(DateTime, server_default=func.now(), \
      server_onupdate=func.current_timestamp())

    def __init__(self, domainname):
        self.domainname = domainname

class Domain(object):

    def __init__(self, server):
        self.server = server
        self.Session = sessionmaker(bind=meta.engine)

    def add(self, name):
        session = self.Session()
        # FIXME: Can we do a merge rather than a query followed by an add?
        try:
            entry = session.query(DomainEntry).\
              filter(DomainEntry.domainname == name).one()
        except  NoResultFound, e:
            entry = DomainEntry(name)
            session.add(entry)
            session.commit()
            session.close()
        finally:
            session.close()

    def id_by_name(self, name):
        session = self.Session()

        # We expect the entry to exist, so allow a NoResultFound
        # exception to percolate up if the entry is not found.
        entry = session.query(DomainEntry).\
          filter(DomainEntry.domainname == name).one()

        return entry.domainid
