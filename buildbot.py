# hgbuildbot.py - mercurial hooks for buildbot
#
# Copyright 2007 Frederic Leroy <fredo@starox.org>
# Adapted for Python 2010 Georg Brandl <georg@python.org>
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.

# hook extension to send change notifications to buildbot when a changeset is
# brought into the repository from elsewhere.
#
# default mode is to use mercurial branch
#
# to use, configure hgbuildbot in .hg/hgrc like this:
#
#   [hooks]
#   changegroup = python:buildbot.changes.hgbuildbot.hook
#
#   [hgbuildbot]
#   # config items go in here
#
# config items:
#
# REQUIRED:
#   master = host:port                   # host to send buildbot changes
#
# OPTIONAL:
#   prefix = prefix/                     # prefix for all file names

import os
import sys

from mercurial.i18n import gettext as _
from mercurial.node import bin, hex, nullid
from mercurial.context import workingctx

# mercurial's on-demand-importing hacks interfere with the:
#from zope.interface import Interface
# that Twisted needs to do, so disable it.
try:
    from mercurial import demandimport
    demandimport.disable()
except ImportError:
    pass

sys.path.append('/data/buildbot/lib/python')

from buildbot.clients import sendchange
from twisted.internet import defer, reactor


def hook(ui, repo, hooktype, node=None, source=None, **kwargs):
    # read config parameters
    master = ui.config('hgbuildbot', 'master')
    if not master:
        ui.write("* You must add a [hgbuildbot] section to .hg/hgrc in "
                 "order to use buildbot hook\n")
        return
    prefix = ui.config('hgbuildbot', 'prefix', '')

    if hooktype != 'changegroup':
        ui.status('hgbuildbot: hook %s not supported\n' % hooktype)

    s = sendchange.Sender(master, None)
    d = defer.Deferred()
    reactor.callLater(0, d.callback, None)
    # process changesets
    def _send(res, c):
        ui.status("rev %s sent\n" % c['revision'])
        return s.send(c['branch'], c['revision'], c['comments'],
                      c['files'], c['username'])

    start = repo[node].rev()
    end = len(repo)
    for rev in xrange(start, end):
        # send changeset
        node = repo.changelog.node(rev)
        manifest, user, (time, timezone), files, desc, extra = repo.changelog.read(node)
        parents = [p for p in repo.changelog.parents(node) if p != nullid]
        branch = extra['branch']
        # merges don't always contain files, but at least one file is required by buildbot
        if len(parents) > 1 and not files:
            files = ["merge"]
        files = [prefix + f for f in files]
        change = {
            'master': master,
            'username': user,
            'revision': hex(node),
            'comments': desc,
            'files': files,
            'branch': branch,
        }
        d.addCallback(_send, change)

    d.addCallbacks(s.printSuccess, s.printFailure)
    d.addBoth(s.stop)
    s.run()
