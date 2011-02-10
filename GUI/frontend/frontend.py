#!/usr/bin/env python
# -*- coding: utf8 -*-

###
# Copyright (c) 2011, Valentin Lorentz
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
###

# Standard library
from __future__ import print_function
import threading
import hashlib
import socket
import time
import sys

# Third-party modules
from PyQt4 import QtCore, QtGui

# Local modules
import window


sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('localhost', 14789))
sock.settimeout(0.01)

# FIXME: internationalize
_ = lambda x:x


def sendCommand(command):
    """Get a command, send it, and returns a unique hash, used to identify
    replies to this command."""
    hash_ = hashlib.sha1(str(time.time()) + command).hexdigest()
    command = '%s: %s\n' % (hash_, unicode(command).encode('utf8', 'replace'))
    sock.send(command)
    return hash_

class Window(QtGui.QTabWidget, window.Ui_window):
    """Represents the main window."""
    def __init__(self, eventsManager, parent=None):
        QtGui.QWidget.__init__(self, parent)

        self._eventsManager = eventsManager

        self.setupUi(self)
        self.connect(self.commandEdit, QtCore.SIGNAL('returnPressed()'),
                     self.commandSendHandler)
        self.connect(self.commandSend, QtCore.SIGNAL('clicked()'),
                     self.commandSendHandler)

    def commandSendHandler(self):
        """Slot called when the user clicks 'Send' or presses 'Enter' in the
        raw commands tab."""
        command = self.commandEdit.text()
        self.commandEdit.clear()
        try:
            self._eventsManager.hook(sendCommand(command), self.replyReceived)
            s = _('<-- ') + command
        except socket.error:
            s = _('(not sent) <-- ') + command
        self.commandsHistory.appendPlainText(s)

    def replyReceived(self, reply):
        """Called by the events manager when a reply to a raw command is
        received."""
        self.commandsHistory.appendPlainText(_('--> ') + reply.decode('utf8'))

    def displaySpecialMessage(self, message):
        """Called by the events manager when a special message has to be
        displayed."""
        self.commandsHistory.appendPlainText(_('* %s *') % message)



class EventsManager(QtCore.QObject):
    """This class handles all incoming messages, and call the associated
    callback (using hook() method)"""
    def __init__(self):
        self._currentLine = ''
        self._hooks = {} # FIXME: should be cleared every minute

        self._timerGetReplies = QtCore.QTimer()
        self.connect(self._timerGetReplies, QtCore.SIGNAL('timeout()'),
                     self._getReplies);
        self._timerGetReplies.start(100)

    def _getReplies(self):
        """Called by the QTimer; fetches the messages and calls the hooks."""
        currentLine = self._currentLine
        self.currentLine = ''
        if not '\n' in currentLine:
            try:
                data = sock.recv(4096)
            except socket.timeout:
                return
        if not data: # Frontend closed connection
            self._timer.stop()
            self.callbackSpecialMessage(_('connection broken'))
            return
        if '\n' in data:
            splitted = (currentLine + data).split('\n')
            nextLines = '\n'.join(splitted[1:-1])
            splitted = splitted[0].split(': ')
            hash_, reply = splitted[0], ': '.join(splitted[1:])
            assert hash_ in self._hooks
            self._hooks[hash_](reply)
        else:
            nextLines = currentLine + data
        self._currentLine = nextLines

    def hook(self, hash_, callback):
        """Attach a callback to a hash: everytime a reply with this hash is
        received, the callback is called."""
        self._hooks[hash_] = callback

    def unhook(self, hash_):
        """Undo hook()."""
        return self._hooks.pop(hash_)



if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)

    eventsManager = EventsManager()

    window = Window(eventsManager)
    window.show()
    window.commandEdit.setFocus()

    eventsManager.callbackSpecialMessages = window.displaySpecialMessage

    sys.exit(app.exec_())