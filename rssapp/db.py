from __future__ import absolute_import, unicode_literals
import datetime

from sqlalchemy import create_engine, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property, Comparator
from sqlalchemy.orm import scoped_session, sessionmaker, relationship, backref
from sqlalchemy.schema import Column
from sqlalchemy.types import DateTime, Integer, Unicode
from pbkdf2 import crypt

engine = create_engine('sqlite:///app.db')
engine.execute('pragma foreign_keys=on')
session = scoped_session(sessionmaker(bind=engine, autoflush=False))

Base = declarative_base(bind=engine)


### tables
class User(Base):
    __tablename__ = 'User'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode, nullable=False, unique=True)
    _password = Column(Unicode(48), nullable=False)

    feeds = relationship("Feed", order_by="Feed.id", backref="owner")
 
    class crypt_comparator(Comparator):
        def operate(self, op, other, **kw):
            return op(self.__clause_element__(), crypt(other, self.__clause_element__()))
 
    @hybrid_property
    def password(self):
        return self.crypt_comparator(self._password)
 
    @password.setter
    def password(self, value):
        self._password = crypt(value)
 
    @password.comparator
    def password(self):
        return self.crypt_comparator(self._password)


class Feed(Base):
    __tablename__ = 'Feed'
    id = Column(Integer, primary_key=True)
    _owner = Column(Integer, ForeignKey("User.id"), nullable=False)
    name = Column(Unicode, nullable=False)
    feed_url = Column(Unicode, nullable=False)
    link = Column(Unicode, nullable=False)
    ttl = Column(Integer, nullable=False) # minutes?
    next_check = Column(DateTime, nullable=False)
    
class Entry(Base):
    __tablename__ = 'Entry'
    id = Column(Integer, primary_key=True)
    _owner = Column(Integer, ForeignKey("Feed.id"), nullable=False)
    owner = relationship("Feed") # always do a proper query to paginate - slices work at least on queries, dunno these too?

    name = Column(Unicode, nullable=False)
    url = Column(Unicode, nullable=False)
    date = Column(DateTime, nullable=False, index=True)


if __name__ == "__main__":
    from sqlalchemy import create_engine
 
    Base.metadata.create_all(engine)

    foo = session.query(User).filter(User.name == 'foo').all()
    if not foo:
        foo = User(name='foo', password='bar')
        session.add(foo)
        session.commit()
    else:
        print foo
    session.remove()
