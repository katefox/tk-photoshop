# system modules
import logging

# local modules
import flexbase

# setup logging
logger = logging.getLogger('tank.photoshop')


def log_debug(msg, *args, **kwargs):
    logger.debug(msg, *args, **kwargs)


def log_error(msg, *args, **kwargs):
    logger.error(msg, *args, **kwargs)


def log_exception(msg, *args, **kwargs):
    logger.exception(msg, *args, **kwargs)


def clear_panel():
    flexbase.requestClearPanel()


def add_button(label, callback):
    flexbase.requestAddButton(label, callback)


def RemoteObject(cls, *args, **kwargs):
    return flexbase.RemoteObject(cls, *args, **kwargs)


# plugin initialization will call the app setup
def initialize_photoshop_application(remote_port):
    global app
    try:
        flexbase.setup(remote_port)
        app = flexbase.requestStatic('com.adobe.csawlib.photoshop.Photoshop', 'app')
        logger.info("Photoshop version is '%s'", app.version)
    except:
        log_exception('error in initializePhotoshopApplication')
