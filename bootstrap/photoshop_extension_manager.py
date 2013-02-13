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
    # Upgrade if the installed version is out of date
    config = _get_config()
    installed_version = config.get("Adobe Extension", "installed_version")
    if _version_cmp(CURRENT_EXTENSION, installed_version) > 0:
        _upgrade_extension()


def tag():
    config = _get_config()
    config.set("Adobe Extension", "installed_version", CURRENT_EXTENSION)
    _save_config(config)


# - Internal -------------------------------------------------------------------
_APPNAME = "com.shotgunsoftware.TankPython"
_CSIDL_LOCAL_APPDATA = 28


def _get_config():
    # Setup defaults
    config = ConfigParser.SafeConfigParser()
    config.add_section("Adobe Extension")
    config.set("Adobe Extension", "installed_version", "0.0.0")

    # Load the actual config
    config_fname = _get_conf_fname()
    if os.path.exists(config_fname):
        config.read(config_fname)

    return config


def _save_config(config):
    # Create directory for config file if it does not exist
    config_fname = _get_conf_fname()
    config_dir = os.path.dirname(config_fname)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    # Save out the updated config
    fp = open(config_fname, "wb")
    try:
        config.write(fp)
    finally:
        fp.close()


def _get_conf_fname():
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
        args = ['open', '-W', zxp_path]
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
