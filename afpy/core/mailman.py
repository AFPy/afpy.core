# -*- coding: utf-8 -*-
import afpy.core.config
from afpy.ldap import custom as ldap
import subprocess
import tempfile
import os

mailman = lambda cmd: 'LC_ALL=C sudo /var/lib/mailman/bin/%s' % cmd

config = afpy.core.config.get_config()

def getEmail(value):
    if isinstance(value, ldap.User):
        return value.email
    if '@' not in value:
        return ldap.getUser(value).email
    return value


class List(object):

    def __init__(self, name, title, public=False):
        self.name = name
        self.title = title
        self.public = public

    def listMembers(self):
        pipe = subprocess.Popen(
                mailman('list_members %s ' % self.name),
                shell=True, stdout=subprocess.PIPE)
        members = pipe.stdout.readlines()
        return [m.strip() for m in members]

    def __contains__(self, value):
        mail = getEmail(value)
        data = self.listMembers()
        return mail in data

    def append(self, value, options='-w y -a n'):
        mail = getEmail(value)
        self.extend([mail], options)

    def extend(self, mails, options='-w y -a n'):
        fd = tempfile.NamedTemporaryFile(prefix='afpyMailman_')
        filename = fd.name
        for m in mails:
            print >> fd, m
        fd.flush()
        subprocess.call(
             mailman('add_members %s -r %s "%s" > /dev/null' % (
                                            options, filename, self.name)),
             shell=True)
        fd.close()

    def __delitem__(self, value):
        mail = getEmail(value)
        if mail in self:
            subprocess.call(
                mailman('remove_members -n -N %s %s' % (self.name, mail)),
                shell=True)
        else:
            raise KeyError('%r does not contain %s' % (self, mail))

    def __len__(self):
        return len(self.listMembers())

    def __repr__(self):
        return '<Liste at %s>' % self.name


class Lists(object):
    """ mailing lists::

        liste = Lists()[name]
        name in List()
        Lists().getListsFor(email)
    """
    lists = dict(
        [(k, List(k, v, False)) for k,v in config.items('private_lists')] + \
        [(k, List(k, v, True)) for k, v in config.items('public_lists')])
    labels = dict([(v.name, k) for k,v in lists.items()])

    def keys(self):
        return self.lists.keys()

    def values(self):
        return self.lists.values()

    def __getitem__(self, name):
        name = self.labels.get(name, name)
        if name in self.keys():
            return self.lists[name]
        raise KeyError('No list named %s' % name)

    def __contains__(self, name):
        name = self.labels.get(name, name)
        return name in self.keys()

    def __delitem__(self, value):
        mail = getEmail(value)
        for name in self.getListsFor(mail):
            del self[name][mail]

    def getListsFor(self, value):
        mail = getEmail(value)
        pipe = subprocess.Popen(
                mailman('find_member %s' % mail),
                shell=True, stdout=subprocess.PIPE)
        members = pipe.stdout.readlines()
        members = [m.strip() for m in members]
        return [self.labels.get(m,m) for m in members if m in self.labels]

lists = Lists()

def subscribeTo(name, user):
    """ @name: list name
    @user: ldap.User instance
    """
    ml = lists[name]
    email = user.email
    try:
        if email not in ml.listMembers():
            ml.append(email)
            return 0
    except:
        return 1
    return -1

def unsubscribeTo(name, user):
    """ @name: list name
    @user: ldap.User instance
    """
    ml = lists[name]
    email = user.email
    try:
        if email in ml.listMembers():
            del ml[email]
            return 0
    except:
        return 1
    return -1

def switchEmail(old, new):
    """change email in all lists
    @old: old email
    @new: new email
    """
    for name in lists.getListsFor(old):
        ml = lists[name]
        del ml[old]
        ml.append(new, options='-w n')

