#
# Copyright (c) 2013 Shotgun Software, Inc
# ----------------------------------------------------
#
import os
import re
import sys
import subprocess
import ConfigParser

CURRENT_EXTENSION = "0.1.1"
ENV_VAR = "TANK_PHOTOSHOP_EXTENSION_MANAGER"


def update():
    # Setup defaults
    config = ConfigParser.SafeConfigParser()
    config.add_section("Adobe Extension")
    config.set("Adobe Extension", "installed_version", "0.0.0")

    # Load the actual config
    config_fname = _get_conf_file()
    if os.path.exists(config_fname):
        config.read(config_fname)
    installed_version = config.get("Adobe Extension", "installed_version")

    # And upgrade if the installed version is out of date
    if _version_cmp(CURRENT_EXTENSION, installed_version) > 0:
        _upgrade_extension()
        config.set("Adobe Extension", "installed_version", CURRENT_EXTENSION)

        # Create directory for config file if it does not exist
        config_dir = os.path.dirname(config_fname)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        # Save out the updated config
        with open(config_fname, "wb") as fp:
            config.write(fp)


# - Internal -------------------------------------------------------------------
_APPNAME = "com.shotgunsoftware.TankPython"
_CSIDL_LOCAL_APPDATA = 28


def _get_conf_file():
    if sys.platform == "win32":
        return _get_win_fname()
    elif sys.platform == "darwin":
        return _get_osx_fname()
    else:
        raise ValueError("unsupported platform: %s" % sys.platform)


def _get_osx_fname():
    folder = os.path.join(os.path.expanduser('~/Library/Application Support/'), _APPNAME)
    return os.path.join(folder, "TankPython.ini")


def _get_win_fname():
    import ctypes

    bfr = ctypes.create_unicode_buffer(1024)
    ctypes.windll.shell32.SHGetFolderPathW(None, _CSIDL_LOCAL_APPDATA, None, 0, bfr)

    # Fix to get short path name when invalid unicode is used
    needs_fix = False
    for c in bfr:
        if ord(c) > 255:
            needs_fix = True
            break
    if needs_fix:
        fix_bfr = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.kernel32.GetShortPathNameW(bfr.value, fix_bfr, 1024):
            bfr = fix_bfr

    folder = bfr.value
    return os.path.join(folder, "%s.ini" % _APPNAME)


def _version_cmp(left, right):
    def normalize(v):
        return [int(x) for x in re.sub(r'(\.0+)*$', '', v).split(".")]
    return cmp(normalize(left), normalize(right))


def _upgrade_extension():
    # Grab path to extension manager
    try:
        extension_manager = os.environ[ENV_VAR]
    except KeyError:
        raise ValueError("Could not open extension manager from env var %s" % ENV_VAR)

    zxp_path = os.path.normpath(os.path.join(__file__, "..", "..", "Tank.zxp"))
    if sys.platform == "darwin":
        # Run the executable directly from within the bundle
        bundle_path = os.path.join("Contents", "MacOS", os.path.splitext(os.path.basename(extension_manager))[0])
        args = [os.path.join(extension_manager, bundle_path), "-suppress", "-install", 'zxp="%s"' % zxp_path]
    elif sys.platform == "win32":
        args = [extension_manager, "-install", 'zxp="%s"' % zxp_path]
    else:
        raise ValueError("unsupported platform: %s" % sys.platform)

    process = subprocess.Popen(args, stdout=subprocess.PIPE)
    output, _ = process.communicate()
    ret = process.poll()
    if ret:
        error = subprocess.CalledProcessError(ret, args[0])
        error.output = output
        raise error

"""
# The below is an attempt to run the install with elevated UAC privs so
# that the return value could be checked.  But I could not get it to work
# so falling back to the above simpler implementation

def _upgrade_extension_win(extension_manager, zxp_path):
    import ctypes
    import ctypes.wintypes

    # Need to run with elevated privs on windows.  It ain't pretty
    INFINITE = -1
    WAIT_FAILED = 0xFFFFFFFF
    WAIT_OBJECT_0 = 0x00000000L
    SEE_MASK_NOCLOSEPROCESS = 0x00000040

    class SHELLEXECUTEINFO(ctypes.Structure):
        _fields_ = (
            ("cbSize", ctypes.wintypes.DWORD),
            ("fMask", ctypes.c_ulong),
            ("hwnd", ctypes.wintypes.HANDLE),
            ("lpVerb", ctypes.c_char_p),
            ("lpFile", ctypes.c_char_p),
            ("lpParameters", ctypes.c_char_p),
            ("lpDirectory", ctypes.c_char_p),
            ("nShow", ctypes.c_int),
            ("hInstApp", ctypes.wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", ctypes.c_char_p),
            ("hKeyClass", ctypes.wintypes.HKEY),
            ("dwHotKey", ctypes.wintypes.DWORD),
            ("hIconOrMonitor", ctypes.wintypes.HANDLE),
            ("hProcess", ctypes.wintypes.HANDLE),
        )

    ShellExecuteEx = ctypes.windll.shell32.ShellExecuteEx
    ShellExecuteEx.restype = ctypes.wintypes.BOOL

    sei = SHELLEXECUTEINFO()
    sei.cbSize = ctypes.sizeof(sei)
    sei.fMask = SEE_MASK_NOCLOSEPROCESS
    sei.lpVerb = "runas"
    sei.lpFile = extension_manager
    sei.lpParameters = "-install zxp=\\\"\\\"\\\"%s\\\"\\\"\\\"" % zxp_path
    sei.nShow = 0
    ret = bool(ShellExecuteEx(ctypes.byref(sei)))

    # Initial call failed entirely
    if not ret:
        error = subprocess.CalledProcessError(ret, extension_manager)
        raise error

    # A valid process was not created
    ret = ctypes.cast(sei.hInstApp, ctypes.c_void_p).value
    if not ret > 32:
        error = subprocess.CalledProcessError(ret, extension_manager)
        raise error

    # No handle was returned
    if sei.hProcess is None:
        error = subprocess.CalledProcessError(ret, extension_manager)
        raise error

    # Wait for the run to finish
    ret = ctypes.windll.kernel32.WaitForSingleObject(sei.hProcess, INFINITE)
    if ret == WAIT_FAILED:
        raise ctypes.WinError()

    # Now get the real return value
    ret = ctypes.c_int(0)
    p_ret = ctypes.pointer(ret)
    win_ret = ctypes.windll.kernel32.GetExitCodeProcess(sei.hProcess, p_ret)

    # See if get exit code worked
    if win_ret == 0:
        raise ctypes.WinError()

    # And finally the actual return code
    if not ret == 0:
        error = subprocess.CalledProcessError(ret, extension_manager)
        raise error

    # clean up
    ret = ctypes.windll.kernel32.CloseHandle(sei.hProcess)
    if ret == 0:
        raise ctypes.WinError()
"""
