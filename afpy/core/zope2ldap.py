# -*- coding: utf-8 -*-
import os, sys, logging, xmlrpclib
from afpy.core import config, ldap

server = xmlrpclib.Server('%s/ldap/' % config.zope_admin_url())

def getUIDS():
    """get usernames from zope
    """
    uids = server.getUIDS()
    uids = [u for u in uids if not u.startswith('group_')]
    uids = [u for u in uids if not u.startswith('gr_')]
    return uids

def updateUID(uid):
    """add or update a member
    """
    datas = server.getUID(uid)
    if not datas:
        logging.error('%s dos not exist' % uid)
        return {}

    password = datas.get('__passwd')
    del datas['__passwd']

    first_date = datas.get('first_date')
    if first_date:
        del datas['first_date']

    m_year = []
    if 'years' in datas:
        years = datas['years']
        for year in years:
            if first_date:
                if first_date.startswith(year):
                    m_year.append(first_date)
                    continue
                else:
                    m_year.append('%s0101000000Z' % year)
        del datas['years']

    if ldap.isUser(uid):
        ldap.updateUser(uid, **datas)
        ldap.changePassword(uid, password)
        #logging.warn('%s updated' % uid)
    else:
        ldap.addUser(uid, **datas)
        ldap.changePassword(uid, password)
        logging.warn('%s added' % uid)

    #res = ldap.conn.admin().search(ldap.getDN(uid),
    #                          'sub', filter='(objectClass=payment)')
    #for rdn, payment in res:
    #    try:
    #        ldap.conn.admin().delete(rdn)
    #    except:
    #        pass
    #for y in m_year:
    #    ldap.addPayment(uid, y, '20')

    return datas

def main():
    uids = getUIDS()
    for uid in uids:
        updateUID(uid)
