import os
import sys
import logging
import logging.handlers

# setup logging
################################################################################
log_dir = '%s/Library/Logs/Shotgun/' % os.path.expanduser('~')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
rotating = logging.handlers.RotatingFileHandler(os.path.join(log_dir, 'tk-photoshop.log'), maxBytes=4*1024*1024, backupCount=10)
rotating.setFormatter(logging.Formatter('%(asctime)s [%(levelname) 8s] %(threadName)s %(name)s: %(message)s'))
logger = logging.getLogger('tank')
logger.addHandler(rotating)
logger.setLevel(logging.DEBUG)

logger = logging.getLogger('tank.photoshop.PythonBootstrap')
logger.info('================================== Initializing Python Interpreter ===================================')

# setup default exception handling to log
def logging_excepthook(type, value, tb):
    logger.exception("Uncaught exception", exc_info=(type, value, tb))
    sys.__excepthook__(type, value, tb)
sys.execpthook = logging_excepthook

# setup sys path to include photoshop
################################################################################
sys.path.insert(0, os.path.dirname(__file__))

# initalize photoshop
################################################################################
try:
    import photoshop
    remote_port = int(sys.argv[1])
    photoshop.initialize_photoshop_application(remote_port)
except Exception, e:
    logger.exception('Failed to initialize photoshop app')
    sys.exit(1)


# Startup PySide
################################################################################
from PySide import QtGui
from PySide import QtCore
import logging_console

g_resourceDir = os.path.join(os.path.dirname(__file__), "resources")

# create global app
sys.argv[0] = 'Tank Photoshop'
g_app = QtGui.QApplication(sys.argv)
g_app.setQuitOnLastWindowClosed(False)
g_app.setWindowIcon(QtGui.QIcon(os.path.join(g_resourceDir, "app.png")))
g_app.setApplicationName(sys.argv[0])

# update style
QtGui.QApplication.setStyle("cleanlooks")
qss_file = os.path.join(g_resourceDir, "style.qss")
f = open(qss_file)
qss = f.read()
f.close()
g_app.setStyleSheet(qss)

# invisible top level window to allow the app to come to the foreground
g_win = QtGui.QWidget()
g_win.setWindowFlags(QtCore.Qt.FramelessWindowHint)
g_win.setAttribute(QtCore.Qt.WA_TranslucentBackground)
g_app.setProperty("tk-photoshop.top_level_window", g_win)
g_win.show()

# logging console
g_log = logging_console.LogConsole()
g_app.setProperty("tk-photoshop.log_console", g_log)
qt_handler = logging_console.QtLogHandler(g_log.logs)
logger = logging.getLogger('tank')
logger.addHandler(qt_handler)
g_log.setHidden(True)

# run userSetup.py if it exists, borrowed from Maya
################################################################################
try:
    for path in sys.path:
        scriptPath = os.path.join(path, 'userSetup.py')
        if os.path.isfile(scriptPath):
            logger.debug('Running "%s"', scriptPath)
            import __main__
            try:
                execfile(scriptPath, __main__.__dict__)
            except:
                logger.exception('Error running "%s"', scriptPath)
except Exception, e:
    logger.exception('Failed to execute userSetup.py')

logger.info("Starting PySide backend application %s", g_app)
sys.exit(g_app.exec_())
