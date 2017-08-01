# -*- coding: utf-8 -*-
import os, stat
from ConfigParser import ConfigParser

def get_config():
    filename = os.path.expanduser('~/.afpy.cfg')
    if not os.path.isfile(filename):
        fd = open(filename, 'w')
        print >> fd, '[ldap]'
        print >> fd, 'binder=test_password'
        print >> fd, '[zope]'
        print >> fd, 'host=localhost'
        print >> fd, 'port=8027'
        print >> fd, 'admin=test_password'
        fd.close()
    os.chmod(filename, stat.S_IRUSR)
    config = ConfigParser()
    config.read(filename)
    return config

def get(section, option):
    config = get_config()
    return config.get(section, option)

def get_passwd(section, option):
    return option, get(section, option)

def ldap_admin():
    return get_passwd('ldap', 'admin')

def ldap_binder():
    return get_passwd('ldap', 'binder')

def zope_admin():
    return get_passwd('zope', 'admin')

def zope_admin_url():
    username, passwd = zope_admin()
    host = get('zope','host')
    port = get('zope', 'port')
    return 'http://%s:%s@%s:%s/afpy/' % (username, passwd, host, port)
