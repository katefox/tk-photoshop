#
# Copyright (c) 2013 Shotgun Software, Inc
# ----------------------------------------------------
#
"""
framework for running callbacks in the main PySide GUI thread

This is used by the logging console to update the gui on the main thread
and so it cannot use logging itself
"""
from PySide import QtCore


class RunCallbackEvent(QtCore.QEvent):
    EVENT_TYPE = QtCore.QEvent.Type(QtCore.QEvent.registerEventType())

    def __init__(self, fn, *args, **kwargs):
        QtCore.QEvent.__init__(self, RunCallbackEvent.EVENT_TYPE)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs


class CallbackRunner(QtCore.QObject):
    def event(self, event):
        # Bring app to the foreground if we can
        app = QtCore.QCoreApplication.instance()
        win = app.property('tk-photoshop.top_level_window')
        win.activateWindow()
        event.fn(*event.args, **event.kwargs)
        # TODO: NEED TO RAISE WINDOWS SOMEHOW
        return True

g_callbackRunner = CallbackRunner()


def send_to_main_thread(fn, *args, **kwargs):
    global g_callbackRunner
    QtCore.QCoreApplication.postEvent(g_callbackRunner, RunCallbackEvent(fn, *args, **kwargs))
