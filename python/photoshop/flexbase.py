#
# Copyright (c) 2013 Shotgun Software, Inc
# ----------------------------------------------------
#
import os
import json
import time
import uuid
import errno
import struct
import socket
import logging
import threading
import xml.etree.cElementTree as etree

from PySide import QtCore

from . import callback_event

PYTHON_REQUEST = 1
PYTHON_RESPONSE = 2
PYTHON_QUIT = 3

PYTHON_CALLBACK = 10004
SET_PORT = 10005

PING = 5  # ENQ
PONG = 6  # ACK


def handle_show_log():
    app = QtCore.QCoreApplication.instance()
    win = app.property('tk-photoshop.log_console')
    win.setHidden(False)
    win.activateWindow()
    win.raise_()


class FlexRequest(object):
    @classmethod
    def setup(cls, remote_port):
        cls.requests = {}
        cls.callbacks = {}
        cls.remote_port = remote_port
        cls.local_port = None
        cls.logger = logging.getLogger('tank.photoshop.flexbase.FlexRequest')
        server = threading.Thread(target=cls.ListenThreadRun, name="FlexListenThread")
        heartbeat = threading.Thread(target=cls.HeartbeatThreadRun, name="HeartbeatThread")
        server.start()
        heartbeat.start()

    @classmethod
    def HeartbeatThreadRun(cls):
        while True:
            time.sleep(0.2)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                s.connect(('127.0.0.1', cls.remote_port))
                s.send(struct.pack("i", PING))
                response = struct.unpack("i", s.recv(struct.calcsize("i")))[0]
                if response != PONG:
                    cls.logger.exception("Python Quitting: Heartbeat unknown response: %s", response)
                    os._exit(1)
            except socket.timeout:
                cls.logger.debug("Python Quitting: Heartbeat timeout")
                os._exit(0)
            except socket.error, e:
                cls.logger.debug("Python Quitting: Heartbeat standard error: %s", errno.errorcode[e.errno])
                os._exit(0)
            except Exception, e:
                cls.logger.exception("Python Quitting: Heartbeat unknown exception")
                os._exit(1)

    @classmethod
    def ListenThreadRun(cls):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('127.0.0.1', 0))
        server.listen(socket.SOMAXCONN)
        cls.local_port = server.getsockname()[1]
        cls.logger.info('listening on port %s', cls.local_port)
        # send the local port back to the plugin
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', cls.remote_port))
        # send in multiple pack calls to avoid alignment issues
        s.send(struct.pack("i", SET_PORT))
        s.send(struct.pack("i", cls.local_port))
        s.close()
        while True:
            (client, _) = server.accept()
            handler = threading.Thread(target=cls.HandleConnection, name="FlexConnectionHandler", args=(client, ))
            handler.start()

    @classmethod
    def HandleConnection(cls, sock):
        type = struct.unpack("i", sock.recv(struct.calcsize("i")))[0]
        if type == PYTHON_RESPONSE:
            xml = ''
            while True:
                buf = sock.recv(4096)
                if not buf:
                    break
                xml += buf
            dom = etree.XML(xml)
            type = dom.find('type').text
            if type == 'requestResponse':
                uid = dom.find('uid').text
                response = dom.find('data').text
                # and send it back to the request
                FlexRequest.requests[uid]['cond'].acquire()
                FlexRequest.requests[uid]['response'] = response
                FlexRequest.requests[uid]['responded'] = True
                FlexRequest.requests[uid]['cond'].notify_all()
                FlexRequest.requests[uid]['cond'].release()
            elif type == 'callback':
                uid = dom.find('uid').text
                cls.logger.debug('callback: %s', uid)
                callback_event.send_to_main_thread(cls.callbacks[uid])
            elif type == 'menu_click':
                menu_id = dom.find('id').text
                if menu_id == 'show_log':
                    callback_event.send_to_main_thread(handle_show_log)
            elif type == 'app_event':
                event = dom.find('event').text
                cls.logger.debug("event: %s", event)
            else:
                cls.logger.error('unknown python request type %s', type)
        else:
            cls.logger.error('unknown event type %d', type)

    def __init__(self, request):
        self.request = request
        self.response = None

    def __call__(self):
        # register this call for the response
        uid = str(uuid.uuid4())
        self.requests[uid] = {
            'cond': threading.Condition(),
            'response': None,
            'responded': False,
        }

        try:
            # build up request xml
            request = etree.Element("request")

            element = etree.Element("uid")
            element.text = str(uid)
            request.append(element)

            element = etree.Element("data")
            element.text = str(self.request)
            request.append(element)

            # send request
            FlexRequest.requests[uid]['cond'].acquire()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('127.0.0.1', self.remote_port))
            s.send(struct.pack("i", PYTHON_REQUEST))
            s.send(etree.tostring(request))
            s.close()

            # wait for response to come through
            self.requests[uid]['cond'].wait(2.0)
            if not self.requests[uid]['responded']:
                self.logger.error("No response to: %s" % uid)
                raise RuntimeError('timeout waiting for response: %s' % self.request)

            # response is now available, grab it
            result = self.requests[uid]['response']
        finally:
            del self.requests[uid]

        return result


def setup(remote_port):
    FlexRequest.setup(remote_port)


def dictToPython(d):
    # Boolean, Date, Error, Function, Vector, XML, XMLList
    if d is None:
        return None
    if d['type'] in ['null', 'undefined']:
        return None
    if d['type'] in ['String', 'Number', 'Boolean', 'int', 'uint']:
        return d['value']
    if d['type'] == 'Array':
        return [dictToPython[e] for e in d['value']]
    if d['type'] == 'RemoteObject':
        return RemoteObject(d['cls'], uid=d['obj_uid'])
    if d['type'] == 'error':
        raise RuntimeError(d['stack'])
    raise ValueError("Unknown reponse object '%s'", d)


def pythonToDict(v):
    if v is None:
        return {'type': 'null'}
    if isinstance(v, str) or isinstance(v, unicode):
        return {'type': 'String', 'value': v}
    if isinstance(v, bool):
        return {'type': 'Boolean', 'value': v}
    if isinstance(v, int):
        return {'type': 'int', 'value': v}
    if isinstance(v, float):
        return {'type': 'Number', 'value': v}
    if isinstance(v, (list, tuple)):
        return {'type': 'Array', 'value': [pythonToDict(e) for e in v]}
    if isinstance(v, RemoteObject):
        return {'type': 'RemoteObject', 'cls': v._cls, 'obj_uid': v._uid}
    raise ValueError("Unhandled python object (%s) '%s'" % (type(v), v))


def requestClearPanel():
    logger = logging.getLogger('tank.photoshop.flexbase')
    logger.debug("requestClearPanel()")
    request = {'type': 'clearpanel'}
    FlexRequest(json.dumps(request))()
    FlexRequest.callbacks.clear()


def requestAddButton(label, callback):
    logger = logging.getLogger('tank.photoshop.flexbase')
    logger.debug("requestAddButton('%s')", label)
    request = {
        'type': 'addbutton',
        'label': label,
    }
    results = FlexRequest(json.dumps(request))()
    results = json.loads(results)
    results = dictToPython(results)
    FlexRequest.callbacks[results] = callback


def requestStatic(cls, prop):
    logger = logging.getLogger('tank.photoshop.flexbase')
    logger.debug("requestStatic('%s', '%s')", cls, prop)
    request = {
        'type': 'static',
        'cls': cls,
        'prop': prop,
    }
    results = FlexRequest(json.dumps(request))()
    results = json.loads(results)
    return dictToPython(results)


def requestClassDesc(cls):
    logger = logging.getLogger('tank.photoshop.flexbase')
    logger.debug("requestClassDesc('%s')", cls)
    request = {
        'type': 'classdef',
        'cls': cls,
    }
    results = FlexRequest(json.dumps(request))()
    try:
        dom = etree.XML(results)
    except Exception:
        raise ValueError("Invalid class description: %s" % results)
    return dom


class RemoteObject(object):
    """A wrapper around a flex object"""
    classMap = {}

    def __init__(self, cls, *args, **kwargs):
        self._logger = logging.getLogger('tank.photoshop.flexbase.RemoteObject')
        if 'uid' in kwargs:
            uid = kwargs['uid']
            del kwargs['uid']
        else:
            uid = None
        if kwargs:
            raise ValueError('unknown arguments to __init__: %s' % kwargs)
        self._cls = cls
        self._dom = self.classMap.setdefault(cls, requestClassDesc(cls))
        if uid is not None and args:
            raise ValueError('cannot specify both uid and init args')
        if uid is not None:
            self._uid = uid
        else:
            self._logger.debug("%s.__init__(%s)", cls, args)
            request = {
                'type': 'objcreate',
                'cls': cls,
                'args': pythonToDict(args)
            }
            results = FlexRequest(json.dumps(request))()
            results = json.loads(results)
            self._uid = results['obj_uid']

    def __repr__(self):
        return "<%s %s>" % (self._cls, self._uid)

    def __getattr__(self, attr):
        self._logger.debug("__getattr__('%s')", attr)

        # check if attr is an accessor
        accessor = None
        accessors = self._dom.findall('factory/accessor')
        for candidate in accessors:
            if candidate.get('name') == attr:
                accessor = candidate
                break
        if accessor is not None:
            if accessor.get('access') == 'writeonly':
                raise ValueError("attempting to access writeonly property '%s'" % attr)
            request = {
                'type': 'getprop',
                'obj': pythonToDict(self),
                'prop': attr,
            }
            results = FlexRequest(json.dumps(request))()
            results = json.loads(results)
            self._logger.debug("__getattr__(%s) = %s", attr, results)
            return dictToPython(results)

        # check if attr is a method
        method = None
        methods = self._dom.findall('factory/method')
        for candidate in methods:
            if candidate.get('name') == attr:
                method = candidate
                break
        if method is not None:
            return RemoteMethod(self, method)

        raise AttributeError("unknown attribute '%s'" % attr)


class RemoteMethod(object):
    def __init__(self, parent, method):
        self._parent = parent
        self._method = method
        self._logger = logging.getLogger('tank.photoshop.flexbase.RemoteMethod')

    def __call__(self, *args):
        name = self._method.get('name')
        request = {
            'type': 'callmethod',
            'obj': pythonToDict(self._parent),
            'method': name,
            'args': pythonToDict(args)
        }
        results = FlexRequest(json.dumps(request))()
        results = json.loads(results)
        self._logger.debug("%s(%s) = %s", name, args, results)
        return dictToPython(results)
