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

from photoshop.flexbase import FlexRequest


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
    # UI
    def _win32_get_photoshop_process_id(self):
        """
        Windows specific method to find the process id of Photoshop.  This
        assumes that it is the parent process of this python process
        """
        if hasattr(self, "_win32_photoshop_process_id"):
            return self._win32_photoshop_process_id
        self._win32_photoshop_process_id = None

        this_pid = os.getpid()

        from tk_photoshop import win_32_api
        self._win32_photoshop_process_id = win_32_api.find_parent_process_id(this_pid)

        return self._win32_photoshop_process_id

    def _win32_get_photoshop_main_hwnd(self):
        """
        Windows specific method to find the main Photoshop window
        handle (HWND)
        """
        if hasattr(self, "_win32_photoshop_main_hwnd"):
            return self._win32_photoshop_main_hwnd
        self._win32_photoshop_main_hwnd = None

        # find photoshop process id:
        ps_process_id = self._win32_get_photoshop_process_id()

        if ps_process_id != None:
            # get main application window for photoshop process:
            from tk_photoshop import win_32_api
            found_hwnds = win_32_api.find_windows(process_id=ps_process_id, class_name="Photoshop", stop_if_found=False)
            if len(found_hwnds) == 1:
                self._win32_photoshop_main_hwnd = found_hwnds[0]

        return self._win32_photoshop_main_hwnd

    def _win32_get_proxy_window(self):
        """
        Windows specific method to get the proxy window that will 'own' all Tank dialogs.  This
        will be parented to the main photoshop application.  Creates the proxy window
        if it doesn't already exist.
        """
        if hasattr(self, "_win32_proxy_win"):
            return self._win32_proxy_win
        self._win32_proxy_win = None

        # get the main Photoshop window:
        ps_hwnd = self._win32_get_photoshop_main_hwnd()
        if ps_hwnd != None:

            from PySide import QtGui
            from tk_photoshop import win_32_api

            # create the proxy QWidget:
            self._win32_proxy_win = QtGui.QWidget()
            self._win32_proxy_win.setWindowTitle('sgtk dialog owner proxy')

            proxy_win_hwnd = win_32_api.qwidget_winid_to_hwnd(self._win32_proxy_win.winId())

            # set no parent notify:
            win_ex_style = win_32_api.GetWindowLong(proxy_win_hwnd, win_32_api.GWL_EXSTYLE)
            win_32_api.SetWindowLong(proxy_win_hwnd, win_32_api.GWL_EXSTYLE, 
                                     win_ex_style 
                                     | win_32_api.WS_EX_NOPARENTNOTIFY)

            # parent to photoshop application window:
            win_32_api.SetParent(proxy_win_hwnd, ps_hwnd)

        return self._win32_proxy_win

    def _create_dialog(self, title, bundle, widget_class, *args, **kwargs):
        """
        Create the standard Tank dialog, with ownership assigned to the main photoshop
        application window if possible.

        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget_class: The class of the UI to be constructed. This must derive from QWidget.

        Additional parameters specified will be passed through to the widget_class constructor.

        :returns: the created widget_class instance
        """
        from tank.platform.qt import tankqdialog

        # first construct the widget object
        obj = widget_class(*args, **kwargs)

        # determine the parent widget to use:
        parent_widget = None
        if sys.platform == "win32":
            # for windows, we create a proxy window parented to the
            # main application window that we can then set as the owner
            # for all Tank dialogs
            parent_widget = self._win32_get_proxy_window()

        # now construct the dialog:
        dialog = tankqdialog.TankQDialog(title, bundle, obj, parent_widget)
        FlexRequest.ActivatePython()
        dialog.raise_()
        dialog.activateWindow()

        # keep a reference to all created dialogs to make GC happy
        if dialog:
            self.__created_qt_dialogs.append(dialog)

        return dialog, obj

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
        debug_force_modal = False  # debug switch for testing modal dialog
        if debug_force_modal:
            status, obj = self.show_modal(title, bundle, widget_class, *args, **kwargs)
            return obj
        else:
            dialog, obj = self._create_dialog(title, bundle, widget_class, *args, **kwargs)
            dialog.show()
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
        from PySide import QtGui
        
        dialog, obj = self._create_dialog(title, bundle, widget_class, *args, **kwargs)
        FlexRequest.ActivatePython()
        dialog.raise_()
        dialog.activateWindow()

        status = QtGui.QDialog.Rejected
        if sys.platform == "win32":
            from tk_photoshop import win_32_api

            saved_state = []
            try:
                # find all photoshop windows and save enabled state:
                ps_process_id = self._win32_get_photoshop_process_id()
                if ps_process_id != None:
                    found_hwnds = win_32_api.find_windows(process_id=ps_process_id, stop_if_found=False)
                    for hwnd in found_hwnds:
                        enabled = win_32_api.IsWindowEnabled(hwnd)
                        saved_state.append((hwnd, enabled))
                        if enabled:
                            win_32_api.EnableWindow(hwnd, False)

                # show dialog:
                status = dialog.exec_()
            except Exception, e:
                self.log_error("Error showing modal dialog: %s", e)
            finally:
                # kinda important to ensure we restore other window state:
                for hwnd, state in saved_state:
                    if win_32_api.IsWindowEnabled(hwnd) != state:
                        win_32_api.EnableWindow(hwnd, state)
        else:
            # show dialog:
            status = dialog.exec_()

        return status, obj

    ##########################################################################################
    # logging

    def _init_logging(self):
        tank_logger = logging.getLogger('tank')
        if self.get_setting("debug_logging", False):
            tank_logger.setLevel(logging.DEBUG)
        else:
            tank_logger.setLevel(logging.INFO)

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
