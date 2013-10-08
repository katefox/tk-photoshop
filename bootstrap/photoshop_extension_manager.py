# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import re
import sys
import subprocess
import ConfigParser

CURRENT_EXTENSION = "0.2.0"
CURRENT_ZXP_PATH = os.path.normpath(os.path.join(__file__, "..", "..", "SgTkPhotoshopEngine.zxp"))

VERSION_BEFORE_RENAME = "0.1.2"
EXTENSION_NAME = "Shotgun Photoshop Engine"

ENV_VAR = "SGTK_PHOTOSHOP_EXTENSION_MANAGER"


def update():
    # Upgrade if the installed version is out of date
    config = _get_config()
    installed_version = config.get("Adobe Extension", "installed_version")
    if _version_cmp(CURRENT_EXTENSION, installed_version) > 0:
        if _version_cmp(VERSION_BEFORE_RENAME, installed_version) >= 0:
            uninstall_old = True
        else:
            uninstall_old = False
        _upgrade_extension(uninstall_old)


def tag(version):
    config = _get_config()
    config.set("Adobe Extension", "installed_version", version)
    _save_config(config)


# - Internal -------------------------------------------------------------------
_APPNAME = "com.shotgunsoftware.SgTkPhotoshopEngine"
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
    return os.path.join(folder, "Extension.ini")


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


def _upgrade_extension(uninstall = False):
    # Grab path to extension manager
    try:
        extension_manager = os.environ[ENV_VAR]
    except KeyError:
        raise ValueError("Could not open extension manager from env var %s" % ENV_VAR)

    if sys.platform == "darwin":
        args = [os.path.join(extension_manager, "Contents", "MacOS", "Adobe Extension Manager CS6")]
        if uninstall:
            args.extend(["-remove", 'product="Photoshop CS6"', 'extension="Shotgun Photoshop Engine"'])
        calls = [args]
    elif sys.platform == "win32":
        calls = []
        if uninstall:
            calls.append([extension_manager, "-remove", 'product="Photoshop CS6 32"', 'extension="Shotgun Photoshop Engine"'])
    else:
        raise ValueError("unsupported platform: %s" % sys.platform)

    if sys.platform == "darwin":
        args = [os.path.join(extension_manager, "Contents", "MacOS", "Adobe Extension Manager CS6")]
    elif sys.platform == "win32":
        args = [extension_manager]

    args.extend(["-install", 'zxp="%s"' % CURRENT_ZXP_PATH])
    calls.append(args)

    # Run each command as its own Extension Manager call because it doesn't handle multiple
    # commands within a single call well.
    for args in calls:
        # Note: Tie stdin to a PIPE as well to avoid this python bug on windows
        # http://bugs.python.org/issue3905
        try:
            process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            process.stdin.close()

            # Popen.communicate() doesn't play nicely if the stdin pipe is closed
            # as it tries to flush it causing an 'I/O error on closed file' error
            # when run from a terminal
            #
            # to avoid this, lets just poll the output from the process until
            # it's finished
            output_lines = []
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                output_lines.append(line)
            ret = process.poll()
        except StandardError:
            import traceback
            ret = True
            output_lines = traceback.format_exc().split()

        if ret:
            # Return value of Extension manager is not reliable, so just warn
            print "WARNING: Extension manager returned a non-zero value."
            print "\n".join(output_lines)
