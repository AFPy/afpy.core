# -*- coding: utf-8 -*-
import os
import re
import sys
import urllib
import urllib2
import string
import socket
import cPickle
import xmlrpclib
from afpy.core import ldap
from afpy.core import config
from afpy.core.countries import COUNTRIES
import re

def ldap2trac():
    # update trac perms
    cmd = 'trac-admin /var/projects/afpy/tracs/%s/ permission add %s TRAC_ADMIN > /dev/null'
    svn_uids = ldap.getMembersOf('svn')
    for trac in ('misc','portal'):
        for uid in svn_uids:
            os.system(cmd % (trac, uid))

def ldap2postfix():
    # alias from cfg
    cfg =config.get_config()
    aliases = dict(cfg.items('mail_aliases'))

    # set canonicals / virtual
    canonical = open('/etc/postfix/ldap_canonical','w')
    virtual = open('/etc/postfix/ldap_virtual','w')

    # for aliases
    members = [m[1] for m in ldap.search('emailAlias=*@afpy.org')]
    emails = [(m['mail'][0],m['emailAlias'][0]) for m in members]
    for email, alias in emails:
        if not email.endswith('@afpy.org'):
            print >> canonical, '%s %s' % (email, alias)
            print >> virtual, '%s %s' % (alias, email)

    # for bureau
    members = [ldap.getUser(u) for u in ldap.getMembersOf('bureau')]
    for u in members:
        if u.title not in aliases:
            print >> virtual, '%s@afpy.org %s' % (u.title, u.mail)
    # aliases
    for alias, email in aliases.items():
        if '@' not in alias:
            alias += '@afpy.org'
        print >> virtual, '%s %s' % (alias, email)

    canonical.close()
    virtual.close()
    os.system('postmap /etc/postfix/ldap_canonical')
    os.system('postmap /etc/postfix/ldap_virtual')

def ldap2map():
    """store google maps coords in a dumped dict
    """
    api_key = config.get('api_keys', 'maps.google.com')
    filename = '/tmp/google.maps.coords.dump'
    users = [ldap.ldap2dict(v[1]) for v in ldap.search('(&(postalCode=*)(street=*))',
                attrs=['postalCode', 'st'])]
    addresses = {}
    for user in users:
        try:
            short_address = '%s, %s' % (
                user['postalCode'].strip(),
                user['st'].strip())
            addresses[short_address] = ''
        except:
            pass

    if os.path.isfile(filename):
        coords = cPickle.load(open(filename))
    else:
        coords = {}

    opener = urllib2.build_opener()


    for address in addresses:
        if address in coords:
            continue
        cp, country = address.split(', ')
        url = 'http://ws.geonames.org/postalCodeLookupJSON?postalcode=%s&country=%s' % (
                cp, country)
        request = urllib2.Request(url)
        request.add_header('User-Agent',
                           'Mozilla Firefox')
        datas = opener.open(request).read()
        coord = eval(datas)
        if coord and coord.get('postalcodes'):
            codes = coord.get('postalcodes')
            if codes:
                coords[address] = codes[0]
    cPickle.dump(coords, open(filename, 'w'))

def check_invalid_email_domain():
    i = 0
    errors = []
    c = 0
    _re = re.compile(r'[0-9]{1,}')
    server = xmlrpclib.Server('%s/ldap/' % config.zope_admin_url())
    for l in string.ascii_lowercase:
        results = ldap.search('mail=%s*' % l, ['mail'])
        c += len(results)
        for res in results:
            dn, mail = res
            mail = mail['mail'][0]
            domain = mail.split('@')[1]
            if _re.match(domain):
                i += 1
                c -= 1
                if domain not in errors:
                    errors.append(domain)
                uid = dn.split(',')[0].split('=')[1]
                #ldap.delUser(uid)
                #server.manage_User('delete', uid)
                print dn, uid, mail
            try:
                socket.gethostbyname(domain)
            except socket.error, e:
                i += 1
                c -= 1
                if domain not in errors:
                    errors.append(domain)
                uid = dn.split(',')[0].split('=')[1]
                #ldap.delUser(uid)
                #server.manage_User('delete', uid)
                print dn, uid, mail, e
    for d in errors:
        print d
    print '%s adresses foireuses, %s domains' % (i, len(errors))
    print '%i comptes' % c

def main():
    ldap2trac()
    ldap2postfix()
    ldap2map()
