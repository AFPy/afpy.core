# -*- coding: utf-8 -*-

import os
import sys
import _ldap
import logging
import datetime
from ldapadapter.utility import LDAPAdapter
from ldapadapter.interfaces import NoSuchObject, InvalidCredentials
from afpy.core import config
from afpy.core.countries import COUNTRIES

DONATION = 'donation'
PERSONNAL_MEMBERSHIP = 'personnal membership'
STUDENT_MEMBERSHIP = 'student membership'
CORPORATE_MEMBERSHIP = 'corporate membership'

PAYMENTS_LABELS = (DONATION, PERSONNAL_MEMBERSHIP, STUDENT_MEMBERSHIP, CORPORATE_MEMBERSHIP)

PAYMENTS_OPTIONS = {
        DONATION:'Donation',
        PERSONNAL_MEMBERSHIP:'Cotisation',
        STUDENT_MEMBERSHIP:'Cotisation etudiante',
#        CORPORATE_MEMBERSHIP:'Cotisation entreprise'
}

SUBSCRIBER_FILTER = '(&(objectClass=payment)(!(paymentObject=donation)))'

ATTRS_MAPPING = {
'uid':'Login',
'title':'Role',
'l':'Ville',
'birthDate':'Date de naissance',
'st':'Pays',
'street':'Adresse',
'sn':'Nom',
'emailAlias':'Alias mail',
'labeledURI':'Open id URL',
'postalCode':'Code postal',
'membershipExpirationDate':'Expire',
'telephoneNumber':'Tel.',
}
SORT_ATTRS = ['uid','sn','title','mail','emailAlias', 'labeledURI',
              'telephoneNumber','birthDate',
              'street','postalCode','l','st',
              'membershipExpirationDate']

ALLOWED_ATTRS = ['sn','mail', 'labeledURI',
              'telephoneNumber','birthDate',
              'street','postalCode','l','st']

_date_marker = datetime.datetime.now()

def date2string(date):
    if not date:
        return None
    if type(date) == type(_date_marker):
        date = date.strftime('%Y%m%d000000Z')
    if type(date) in (type(''), type(u'')):
        date = str(date)
        if '/' in date:
            tuple_date = date.split('/')
            if len(tuple_date) == 3:
                if len(tuple_date[0]) == 4:
                    tuple_date = tuple(tuple_date)
                    date = '%s%s%s000000Z' % tuple_date
                    return date
                elif len(tuple_date[2]) == 4:
                    tuple_date = list(tuple_date)
                    tuple_date.reverse()
                    tuple_date = tuple(tuple_date)
                    date = '%s%s%s000000Z' % tuple_date
                    return date
        else:
            if len(date) == 8:
                date = '%s000000Z' % date
                return date
            elif len(date) == 15 and date.endswith('Z'):
                return date
        raise ValueError('Cant parse date (%s)' % date)

def string2date(date):
    if date:
        try:
            if len(date) >= 8:
                year = date[0:4]
                month = date[4:6]
                day = date[6:8]
                date = datetime.datetime(int(year), int(month), int(day))
                return date
        except Exception, e:
            raise e.__class__('%s (%s)' % (str(e), date))

def ldap2dict(props, keys=None):
    for p in props.keys():
        if keys and p not in keys:
            del props[p]
            continue
        if len(props[p]) == 1:
            v = props[p][0]
            if p in ('mail','emailAlias'):
                v = str(v)
            if 'date' in p.lower():
                v = string2date(v)
            if 'amount' in p.lower():
                v = int(v)
            props[p] = v
    return props

def dn2uid(dn):
    values = dn.split(',')
    for v in values:
        if v.startswith('uid='):
            return v.split('=')[1]
    raise ValueError('No uid in %s' % dn)

useSSL = bool(int(config.get('ldap','port')) == 636)

if useSSL:
    # Workaroud the problem of certificate
    _ldap.set_option(_ldap.OPT_X_TLS_REQUIRE_CERT, _ldap.OPT_X_TLS_NEVER)
    _ldap.set_option(_ldap.OPT_REFERRALS, 0)

class conn(object):

    base_dn = 'dc=afpy,dc=org'
    members_dn = 'ou=members,%s' % base_dn
    groups_dn = 'ou=groups,%s' % base_dn

    _da = LDAPAdapter(config.get('ldap', 'host'),
                      int(config.get('ldap', 'port')),
                      useSSL=useSSL)
    _admin = None
    _binder = None

    @classmethod
    def admin(self):
        if self._admin is None:
            username, passwd = config.ldap_admin()
            dn = 'cn=%s,%s' % (username, self.base_dn)
            dn = dn.replace(' ', '')
            self._admin = self._da.connect(dn, passwd)
        return self._admin

    @classmethod
    def binder(self):
        if self._binder is None:
            username, passwd = config.ldap_binder()
            dn = 'cn=%s,%s' % (username, self.base_dn)
            dn = dn.replace(' ', '')
            self._binder = self._da.connect(dn, passwd)
        return self._binder

    @classmethod
    def search(self,*args, **kwargs):
        try:
            res = self.binder().search(*args, **kwargs)
        except NoSuchObject:
            return []
        except Exception, e:
            logging.error('%s (%s %s)' % (e, args, kwargs))
            return []
        else:
            return res

    @classmethod
    def user(self, username, passwd):
        dn = getDN(username)
        return self._da.connect(dn, passwd)

def search(f, attrs=None):
    """@ filter: a ldap filter
    """
    if attrs:
        return conn.search(conn.base_dn, 'sub', f, attrs=attrs)
    return conn.search(conn.base_dn, 'sub', f)

def isUser(uid):
    """return true if user exist
    """
    dn = getDN(uid)
    try:
        res = conn.binder().search(dn, 'base')
    except NoSuchObject:
        return False
    else:
        return True

def getUser(uid):
    return User(uid)


class User(object):

    objectClass = ['top', 'person','associationMember',
                   'organizationalPerson',
                   'inetOrgPerson']

    def __init__(self, uid):
        self.uid = uid
        self.dn = getDN(uid)
        self._groups = None
        self._data = None

    def __eq__(self, user):
        return user.uid == self.uid

    def __ne__(self, user):
        return user.uid != self.uid

    def checkCredentials(self, passwd):
        try:
            return conn.user(self.dn, passwd)
        except InvalidCredentials:
            return False

    @property
    def groups(self):
        if self._groups is not None:
            return self._groups
        f = '(&(objectClass=groupOfNames)(member=%s))' % self.dn
        res = conn.search(conn.groups_dn,'sub',filter=f, attrs=['cn'])
        groups = [str(g['cn'][0]) for dn,g in res]
        self._groups = groups
        return self._groups

    @property
    def email(self):
        """return emailAlias if any or mail"""
        props = self.getMemberData()
        if 'emailAlias' in props and '@afpy.org' in props['emailAlias']:
            return props['emailAlias']
        return props['mail']

    @property
    def st_label(self):
        props = self.getMemberData()
        st = props['st']
        return COUNTRIES.get(st, st)

    @property
    def expired(self):
        """return True if membership is expired
        """
        props = self.getMemberData()
        if 'membershipExpirationDate' in props:
            if props['membershipExpirationDate'] > datetime.datetime.now():
                return False
        return True

    @property
    def membershipExpirationDate(self):
        props = self.getMemberData()
        if 'membershipExpirationDate' in props:
            return props['membershipExpirationDate']
        return None

    def getMemberData(self):
        dn = self.dn

        if self._data is not None:
            return self._data

        try:
            res = conn.search(dn, 'base')
        except NoSuchObject:
            self._data = {}
            return {}

        try:
            props = res[0][1]
        except Exception, e:
            self._data = {}
            return {}

        for k in ['objectClass']:
            if props.has_key(k):
                del props[k]

        for p in props:
            if len(props[p]) == 1:
                v = props[p][0]
                if p in ('mail','emailAlias'):
                    v = str(v)
                if 'date' in p.lower():
                    v = string2date(v)
                props[p] = v
        self._data = props
        return props

    def addPayment(self, paymentDate='', paymentAmount=None,
                        paymentObject='', invoiceReference=''):

        if not paymentDate:
            paymentDate = datetime.datetime.now()
        paymentDate = date2string(paymentDate)

        if not paymentObject:
            paymentObject = PERSONNAL_MEMBERSHIP

        dn = 'paymentDate=%s,%s' % (paymentDate,self.dn)
        properties = {'objectClass':['top', 'payment'],
                      'paymentDate':[paymentDate],
                      'paymentObject':[paymentObject]}

        if paymentAmount:
            properties['paymentAmount'] = [paymentAmount]
        if invoiceReference:
            properties['invoiceReference'] = [invoiceReference]

        try:
            conn.admin().add(dn, properties)
        except Exception, e:
            logging.error('%s %s %s' % (dn, e, properties))
        else:
            if paymentAmount and int(paymentAmount) > 0:
                updateExpirationDate(self.uid)
        return dn

    def getPayments(self):
        filter = '(objectClass=payment)'
        res = conn.search(self.dn,'sub',
                          filter=filter)
        payments = [(string2date(d['paymentDate'][0]),d) for m, d in res]
        payments = sorted(payments)
        value = lambda d,k, default: d.get(k, [default])[0]
        keys = ['invoiceReference',
                'paymentAmount',
                'paymentDate',
                'paymentObject']
        payments = [ldap2dict(d, keys=keys) for m, d in payments]
        return payments

    def lastRealPayment(self):
        payments = self.getPayments()
        if payments:
            payments = [p for p in payments if p.get('paymentAmount', 0) > 0]
            if payments:
                return payments.pop()
        return dict()

    def getMemberDataForDisplay(self):
        data = self.getMemberData()
        res = []
        for k in SORT_ATTRS:
            v = data.get(k,'')
            if v and 'date' in k.lower():
                v = v.strftime('%d/%m/%Y')
            res.append((ATTRS_MAPPING.get(k,k),v))
        return res

    def edit(self, **kwargs):
        properties = {'objectClass': self.objectClass,
                      'uid':[self.uid.lower()]}
        for k, v in kwargs.items():
            if 'date' in k.lower():
                v = date2string(v)
            properties[k] = [v]
        if 'st' not in properties:
            properties['st'] = ['FR']
        try:
            conn.admin().modify(self.dn, properties)
        except Exception, e:
            logging.error('%s %s %s' % (self.uid, e, properties))
        else:
            self._data = None

    def __getattr__(self, attr):
        if self._data is None:
            self.getMemberData()
        if self._data.has_key(attr):
            return self._data[attr]
        raise AttributeError('%s as no attribute %s' % (self.dn,attr))

    def __repr__(self):
        return '<User dn:%s>' % self.dn

def getDN(uid):
    """get full dn
    """
    if 'ou=members,dc=afpy,dc=org' in uid:
        # already a dn
        return uid
    dn = 'uid=%s, ou=members, dc=afpy, dc=org' % uid.lower()
    dn = dn.replace(' ', '')
    return dn

def getAdherents(min=365, max=None):
    """ return users with a payment > now - min and < now - max
    """
    min = date2string(datetime.datetime.now()-datetime.timedelta(min))
    f = '(&%s(paymentAmount=*))' % SUBSCRIBER_FILTER
    if max:
        max = date2string(datetime.datetime.now()-datetime.timedelta(max))
        f = '(&%s(&(paymentDate>=%s)(paymentDate<=%s)))' % (f, min,max)
    else:
        f = '(&%s(paymentDate>=%s))' % (f, min)
    res = conn.search(conn.members_dn,'sub',filter=f)
    members = [m[0] for m in res]
    members = [m.split(',')[1].split('=')[1] for m in members]
    return set(members)

def getAllTimeAdherents():
    """return users with at least one payment
    """
    return set([p[0].split(',')[1].split('=')[1] for p in conn.search(
                        conn.members_dn, 'sub', 'objectClass=payment')])

def getExpiredUsers():
    """return unregulirised users
    """
    members = getAllTimeAdherents() - getAdherents()
    members = [User(m) for m in members]
    return members

def updateExpirationDate(uid=None):
    filter = '(paymentAmount=*)'
    filter = '(&%s%s)' % (SUBSCRIBER_FILTER, filter)
    if uid:
        dn = getDN(uid)
    else:
        dn = conn.members_dn
    res = conn.search(dn,'sub',
          filter=filter, attrs=['paymentDate', 'paymentAmount'])
    members = [(m.split(',')[1].split('=')[1],
                string2date(d['paymentDate'][0])) for m, d in res \
                if d['paymentAmount'][0] > 0]
    last = {}
    for uid, date in members:
        if not last.has_key(uid):
            last.setdefault(uid, date)
            continue
        if date > last[uid]:
            last[uid] = date
    for uid, date in last.items():
        expire = date+datetime.timedelta(400)
        User(uid).edit(membershipExpirationDate=expire)
        #logging.warn('expire set to %s for %s' % (uid, expire))
    return last

def getMembersOf(uid):
    dn = 'cn=%s, ou=groups, dc=afpy, dc=org' % uid
    dn = dn.replace(' ', '')
    return _getMembersOf(dn)

def _getMembersOf(dn):
    try:
        res = conn.search(dn, 'base')
    except NoSuchObject:
        return []
    else:
        try:
            members = res[0][1]['member']
        except IndexError:
            return []
        members = [m.split(',')[0].split('=')[1] for m in members]
        return members

def setMembersOf(uid, members):
    dn = 'cn=%s, ou=groups, dc=afpy, dc=org' % uid
    dn = dn.replace(' ', '')
    return _setMembersOf(dn, members)

def _setMembersOf(dn, uids):
    members = [getDN(uid) for uid in uids]
    conn.admin().modify(dn, {'member':members})
    return _getMembersOf(dn)

def changePassword(uid, pwd):
    dn = getDN(uid)
    #if '"' in pwd:
    #    logging.error('cant change password for %s' % uid)
    #    return

    host = config.get('ldap', 'host')
    username, passwd = config.ldap_admin()
    bind_dn = 'cn=%s, dc=afpy, dc=org' % username
    bind_dn = bind_dn.replace(' ', '')
    cmd = 'ldappasswd -h %s -D "%s" -w %s -s %s -x %s' % (host, bind_dn, passwd, repr(pwd), dn)
    try:
        os.system('%s > /dev/null' % cmd)
    except UnicodeEncodeError:
        logging.error('cant change password for %s' % uid)

def addUser(uid, **kwargs):
    """add a user::
    """
    properties = {'objectClass':['top', 'person','associationMember',
                                'organizationalPerson', 'inetOrgPerson'],
                  'sn':[uid], 'cn':[uid], 'uid':[uid]}
    for k, v in kwargs.items():
        if 'date' in k.lower():
            v = date2string(v)
        properties[k] = [v]
    if 'st' not in properties:
        properties['st'] = ['FR']
    dn = getDN(uid)
    conn.admin().add(dn, properties)

def updateUser(uid, **kwargs):
    """add a user::
    """
    User(uid).edit(**kwargs)

def delUser(uid):
    """add a user::
    """
    dn = getDN(uid)
    res = conn.search(dn, 'sub', filter='(objectClass=payment)')
    for rdn, payment in res:
        conn.admin().delete(rdn)
    conn.admin().delete(dn)

