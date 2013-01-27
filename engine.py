#
# Copyright (c) 2013 Shotgun Software, Inc
# ----------------------------------------------------
#
"""
A Photoshop engine for Tank.
"""
import os
import sys
import logging

import tank


###############################################################################################
# The Tank Photoshop engine

class PhotoshopEngine(tank.platform.Engine):
    _logger = logging.getLogger('tank.photoshop.engine')

    ##########################################################################################
    # init and destroy
    def init_engine(self):
        self._init_logging()
        self.log_debug("%s: Initializing...", self)
        self.__created_qt_dialogs = []

    def post_app_init(self):
        import tk_photoshop
        self._panel_generator = tk_photoshop.PanelGenerator(self)
        self._panel_generator.populate_panel()        

    def destroy_engine(self):
        self.log_debug("%s: Destroying...", self)
        self._panel_generator.destroy_panel()

    ##########################################################################################
    # dialog management
    
    def show_dialog(self, title, bundle, widget_class, *args, **kwargs):
        """
        Shows a non-modal dialog window in a way suitable for this engine. 
        The engine will attempt to parent the dialog nicely to the host application.
        
        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget_class: The class of the UI to be constructed. This must derive from QWidget.
        
        Additional parameters specified will be passed through to the widget_class constructor.
        
        :returns: the created widget_class instance
        """
        from tank.platform.qt import tankqdialog 
        from tank.platform.qt import QtCore, QtGui
        
        # first construct the widget object 
        obj = widget_class(*args, **kwargs)
        
        # now create a dialog to put it inside
        # parent it to the active window by default
        parent = QtGui.QApplication.activeWindow()
        dialog = tankqdialog.TankQDialog(title, bundle, obj, parent)
        
        # workaround before parenting with the photoshop window works property
        # just ensure the window sits on top!
        dialog.setWindowFlags( dialog.windowFlags() | QtCore.Qt.WindowStaysOnTopHint )
        
        # keep a reference to all created dialogs to make GC happy
        self.__created_qt_dialogs.append(dialog)
        
        # finally show it        
        dialog.show()
        
        # lastly, return the instantiated class
        return obj
    
    def show_modal(self, title, bundle, widget_class, *args, **kwargs):
        """
        Shows a modal dialog window in a way suitable for this engine. The engine will attempt to
        integrate it as seamlessly as possible into the host application. This call is blocking 
        until the user closes the dialog.
        
        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget_class: The class of the UI to be constructed. This must derive from QWidget.
        
        Additional parameters specified will be passed through to the widget_class constructor.

        :returns: (a standard QT dialog status return code, the created widget_class instance)
        """
        from tank.platform.qt import tankqdialog 
        from tank.platform.qt import QtCore, QtGui
        
        # first construct the widget object 
        obj = widget_class(*args, **kwargs)
        
        # now create a dialog to put it inside
        # parent it to the active window by default
        parent = QtGui.QApplication.activeWindow()
        dialog = tankqdialog.TankQDialog(title, bundle, obj, parent)

        # workaround before parenting with the photoshop window works property
        # just ensure the window sits on top!
        dialog.setWindowFlags( dialog.windowFlags() | QtCore.Qt.WindowStaysOnTopHint )
        
        # keep a reference to all created dialogs to make GC happy
        self.__created_qt_dialogs.append(dialog)
        
        # finally launch it, modal state        
        status = dialog.exec_()
        
        # lastly, return the instantiated class
        return (status, obj)
    
    

    ##########################################################################################
    # logging

    def _init_logging(self):
        if self.get_setting("debug_logging", False):
            self._logger.setLevel(logging.DEBUG)
        else:
            self._logger.setLevel(logging.INFO)

    def log_debug(self, msg, *args, **kwargs):
        self._logger.debug(msg, *args, **kwargs)

    def log_info(self, msg, *args, **kwargs):
        self._logger.info(msg, *args, **kwargs)

    def log_warning(self, msg, *args, **kwargs):
        self._logger.warning(msg, *args, **kwargs)

    def log_error(self, msg, *args, **kwargs):
        self._logger.error(msg, *args, **kwargs)

    def log_exception(self, msg, *args, **kwargs):
        self._logger.exception(msg, *args, **kwargs)
