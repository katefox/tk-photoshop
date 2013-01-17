# log console
import cgi
import logging
import photoshop.callback_event

from PySide import QtGui

COLOR_MAP = {
    'CRITICAL': 'indianred',
    '   ERROR': 'indianred',
    ' WARNING': 'khaki',
    '    INFO': 'lightgray',
}


def append_to_log(widget, text):
    widget.appendHtml(text)
    cursor = widget.textCursor()
    cursor.movePosition(cursor.End)
    cursor.movePosition(cursor.StartOfLine)
    widget.setTextCursor(cursor)
    widget.ensureCursorVisible()


class QtLogHandler(logging.Handler):
    def __init__(self, widget):
        logging.Handler.__init__(self)
        self.widget = widget
        self.formatter = logging.Formatter("%(asctime)s [%(levelname) 8s] %(message)s")

    def emit(self, record):
        message = self.formatter.format(record)
        clean = cgi.escape(message).encode('ascii', 'xmlcharrefreplace')
        for (k, v) in COLOR_MAP.iteritems():
            if ('[%s]' % k) in clean:
                clean = '<font color="%s">%s</font>' % (v, clean)
                break
        photoshop.callback_event.send_to_main_thread(append_to_log, self.widget, "<pre>%s</pre>" % clean)


class LogConsole(QtGui.QWidget):
    def __init__(self, parent=None):
        super(LogConsole, self).__init__(parent)
        self.setWindowTitle('Tank Photoshop Logs')
        self.layout = QtGui.QVBoxLayout(self)
        self.logs = QtGui.QPlainTextEdit(self)
        self.layout.addWidget(self.logs)

        # configure the text widget
        self.logs.setLineWrapMode(self.logs.NoWrap)
        self.logs.setReadOnly(True)
