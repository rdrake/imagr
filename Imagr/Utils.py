# -*- coding: utf-8 -*-
#
#  Utils.py
#  Imagr
#
#  Created by Graham Gilbert on 04/04/2015.
#  Copyright (c) 2015 Graham Gilbert. All rights reserved.
#

import hashlib
import os
import FoundationPlist
import plistlib
import shutil
import urllib
from SystemConfiguration import *
from Foundation import *
from AppKit import *
from Cocoa import *
import tempfile
import subprocess
import threading
import time
import sys
import xml.sax.saxutils
import logging
import urlparse
import socket
import re

from gurl import Gurl

class GurlError(Exception):
    pass

class HTTPError(Exception):
    pass

class CustomThread(threading.Thread):
    '''Class for running a process in its own thread'''

    cmd = None

    def __init__(self, cmd=cmd):
        threading.Thread.__init__(self)
        self.cmd = cmd


    def run(self):
        proc = subprocess.call(self.cmd)
        pass

def header_dict_from_list(array):
    """Given a list of strings in http header format, return a dict.
    If array is None, return None"""
    if array is None:
        return array
    header_dict = {}
    for item in array:
        (key, sep, value) = item.partition(':')
        if sep and value:
            header_dict[key.strip()] = value.strip()
    return header_dict

def post_url(url, post_data, message=None, follow_redirects=False,
            progress_method=None, additional_headers=None):
    """Sends POST data to a URL and then returns the result.
    Accepts the URL to send the POST to, URL encoded data and
    optionally can follow redirects
    """
    temp_file = os.path.join(tempfile.mkdtemp(), 'tempdata')
    options = {'url': url,
               'file': temp_file,
               'follow_redirects': follow_redirects,
               'post_data': post_data,
               'additional_headers': header_dict_from_list(additional_headers),
               'logging_function': NSLog}
    NSLog('gurl options: %@', options)

    connection = Gurl.alloc().initWithOptions_(options)
    stored_percent_complete = -1
    stored_bytes_received = 0
    connection.start()
    try:
        while True:
            # if we did `while not connection.isDone()` we'd miss printing
            # messages and displaying percentages if we exit the loop first
            connection_done = connection.isDone()
            if message and connection.status and connection.status != 304:
                # log always, display if verbose is 1 or more
                # also display in progress field
                NSLog(message)
                if progress_method:
                    progress_method(None, None, message)
                # now clear message so we don't display it again
                message = None
            if (str(connection.status).startswith('2')
                    and connection.percentComplete != -1):
                if connection.percentComplete != stored_percent_complete:
                    # display percent done if it has changed
                    stored_percent_complete = connection.percentComplete
                    NSLog('Percent done: %@', stored_percent_complete)
                    if progress_method:
                        progress_method(None, stored_percent_complete, None)
            elif connection.bytesReceived != stored_bytes_received:
                # if we don't have percent done info, log bytes received
                stored_bytes_received = connection.bytesReceived
                NSLog('Bytes received: %@', stored_bytes_received)
                if progress_method:
                    progress_method(None, None,
                                    'Bytes received: %s'
                                    % stored_bytes_received)
            if connection_done:
                break

    except (KeyboardInterrupt, SystemExit):
        # safely kill the connection then re-raise
        connection.cancel()
        raise
    except Exception, err: # too general, I know
        # Let us out! ... Safely! Unexpectedly quit dialogs are annoying...
        connection.cancel()
        # Re-raise the error as a GurlError
        raise GurlError(-1, str(err))

    if connection.error != None:
        # Gurl returned an error
        NSLog('Download error %@: %@', connection.error.code(),
              connection.error.localizedDescription())
        if connection.SSLerror:
            NSLog('SSL error detail: %@', str(connection.SSLerror))
        NSLog('Headers: %@', str(connection.headers))
        raise GurlError(connection.error.code(),
                        connection.error.localizedDescription())

    if connection.response != None:
        NSLog('Status: %@', connection.status)
        NSLog('Headers: %@', connection.headers)
    if connection.redirection != []:
        NSLog('Redirection: %@', connection.redirection)

    connection.headers['http_result_code'] = str(connection.status)
    description = NSHTTPURLResponse.localizedStringForStatusCode_(
        connection.status)
    connection.headers['http_result_description'] = description

    try:
        os.unlink(temp_file)
        os.rmdir(os.path.dirname(temp_file))
    except (OSError, IOError):
        pass
    if str(connection.status).startswith('2'):
        return connection.headers
    elif connection.status == 304:
        # unchanged on server
        NSLog('Item is unchanged on the server.')
        return connection.headers
    else:
        # there was an HTTP error of some sort
        raise HTTPError(connection.status,
                        connection.headers.get('http_result_description', ''))

def get_url(url, destinationpath, message=None, follow_redirects=False,
            progress_method=None, additional_headers=None):
    """Gets an HTTP or HTTPS URL and stores it in
    destination path. Returns a dictionary of headers, which includes
    http_result_code and http_result_description.
    Will raise GurlError if Gurl returns an error.
    Will raise HTTPError if HTTP Result code is not 2xx or 304.
    If destinationpath already exists, you can set 'onlyifnewer' to true to
    indicate you only want to download the file only if it's newer on the
    server.
    If you set resume to True, Gurl will attempt to resume an
    interrupted download."""

    tempdownloadpath = destinationpath + '.download'
    if os.path.exists(tempdownloadpath):
        os.remove(tempdownloadpath)

    options = {'url': url,
               'file': tempdownloadpath,
               'follow_redirects': follow_redirects,
               'additional_headers': header_dict_from_list(additional_headers),
               'logging_function': NSLog}
    NSLog('gurl options: %@', options)

    connection = Gurl.alloc().initWithOptions_(options)
    stored_percent_complete = -1
    stored_bytes_received = 0
    connection.start()
    try:
        while True:
            # if we did `while not connection.isDone()` we'd miss printing
            # messages and displaying percentages if we exit the loop first
            connection_done = connection.isDone()
            if message and connection.status and connection.status != 304:
                # log always, display if verbose is 1 or more
                # also display in progress field
                NSLog(message)
                if progress_method:
                    progress_method(None, None, message)
                # now clear message so we don't display it again
                message = None
            if (str(connection.status).startswith('2')
                    and connection.percentComplete != -1):
                if connection.percentComplete != stored_percent_complete:
                    # display percent done if it has changed
                    stored_percent_complete = connection.percentComplete
                    NSLog('Percent done: %@', stored_percent_complete)
                    if progress_method:
                        progress_method(None, stored_percent_complete, None)
            elif connection.bytesReceived != stored_bytes_received:
                # if we don't have percent done info, log bytes received
                stored_bytes_received = connection.bytesReceived
                NSLog('Bytes received: %@', stored_bytes_received)
                if progress_method:
                    progress_method(None, None,
                                    'Bytes received: %s'
                                    % stored_bytes_received)
            if connection_done:
                break

    except (KeyboardInterrupt, SystemExit):
        # safely kill the connection then re-raise
        connection.cancel()
        raise
    except Exception, err: # too general, I know
        # Let us out! ... Safely! Unexpectedly quit dialogs are annoying...
        connection.cancel()
        # Re-raise the error as a GurlError
        raise GurlError(-1, str(err))

    if connection.error != None:
        # Gurl returned an error
        NSLog('Download error %@: %@', connection.error.code(),
              connection.error.localizedDescription())
        if connection.SSLerror:
            NSLog('SSL error detail: %@', str(connection.SSLerror))
        NSLog('Headers: %@', str(connection.headers))
        if os.path.exists(tempdownloadpath):
            os.remove(tempdownloadpath)
        raise GurlError(connection.error.code(),
                        connection.error.localizedDescription())

    if connection.response != None:
        NSLog('Status: %@', connection.status)
        NSLog('Headers: %@', connection.headers)
    if connection.redirection != []:
        NSLog('Redirection: %@', connection.redirection)

    temp_download_exists = os.path.isfile(tempdownloadpath)
    connection.headers['http_result_code'] = str(connection.status)
    description = NSHTTPURLResponse.localizedStringForStatusCode_(
        connection.status)
    connection.headers['http_result_description'] = description

    if str(connection.status).startswith('2') and temp_download_exists:
        os.rename(tempdownloadpath, destinationpath)
        return connection.headers
    elif connection.status == 304:
        # unchanged on server
        NSLog('Item is unchanged on the server.')
        return connection.headers
    else:
        # there was an HTTP error of some sort; remove our temp download.
        if os.path.exists(tempdownloadpath):
            try:
                os.unlink(tempdownloadpath)
            except OSError:
                pass
        raise HTTPError(connection.status,
                        connection.headers.get('http_result_description', ''))

def downloadFile(url, additional_headers=None):
    temp_file = os.path.join(tempfile.mkdtemp(), 'tempdata')
    try:
        headers = get_url(url, temp_file, additional_headers=additional_headers)
    except HTTPError, err:
        NSLog("HTTP Error: %@", err)
        return False
    except GurlError, err:
        NSLog("Gurl Error: %@", err)
        return False
    try:
        file_handle = open(temp_file)
        data = file_handle.read()
        file_handle.close()
    except (OSError, IOError):
        NSLog('Couldn\'t read %@', temp_file)
        return False
    try:
        os.unlink(temp_file)
        os.rmdir(os.path.dirname(temp_file))
    except (OSError, IOError):
        pass
    return data


def getPasswordHash(password):
    return hashlib.sha512(password).hexdigest()

def getPlistData(data):
    # Try the user's homedir
    try:
        # NSLog("Trying Home Location")
        homedir = os.path.expanduser("~")
        plist = FoundationPlist.readPlist(os.path.join(homedir, "Library", "Preferences", "com.grahamgilbert.Imagr.plist"))
        return plist[data]
    except:
        pass
    # Try the main prefs
    try:
        # NSLog("Trying System Location")
        plist = FoundationPlist.readPlist(os.path.join("/Library", "Preferences", "com.grahamgilbert.Imagr.plist"))
        return plist[data]
    except:
        pass

    # Hopefully we're in a netboot set, try in /System/Installation/Packages
    try:
        # NSLog("Trying NetBoot Location")
        plist = FoundationPlist.readPlist(os.path.join("/System", "Installation", "Packages", "com.grahamgilbert.Imagr.plist"))
        return plist[data]
    except:
        pass

def getServerURL():
    # Get serial number and machine model
    hardware_info = get_hardware_info()
    SERIAL = hardware_info.get('serial_number', 'UNKNOWN')
    machine_model = hardware_info.get('machine_model', 'UNKNOWN')
    
    # Get IP address
    ip_address = socket.gethostbyname(socket.getfqdn())
    
    # Get MAC address
    cmd = "/sbin/ping -c1 {} && /usr/sbin/arp -n {}".format(ip_address, ip_address)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = proc.communicate()
    mac_address = re.findall(r'([\dA-Fa-f]{2}(?:[-:][\dA-Fa-f]{2}){5})', out)[0]
    
    url = urllib.urlencode({
        "serial": SERIAL,
        "machine_model": machine_model,
        "ip_address": ip_address,
        "mac_address": mac_address
    })
    
    return "{}?{}".format(getPlistData('serverurl'), url)

def getReportURL():
    report_url = getPlistData('reporturl')
    if report_url:
        return report_url
    else:
        return None


def sendReport(status, message):
    hardware_info = get_hardware_info()
    SERIAL = hardware_info.get('serial_number', 'UNKNOWN')

    report_url = getReportURL()
    if report_url and len(message) > 0:
        # Should probably do some validation on the status at some point
        data = {
            'status': status,
            'serial': SERIAL,
            'message': message
        }
        NSLog('Report: %@', data )
        data = urllib.urlencode(data)
        # silently fail here, sending reports is a nice to have, if server is down, meh.
        try:
            post_url(report_url, data)
        except:
            pass

    if len(message) > 0:
        log_message = "[{}] {}".format(SERIAL, message)
        log = logging.getLogger("Imagr")

        if status == 'error':
            log.error(log_message)
        else:
            log.info(log_message)

def launchApp(app_path):
    # Get the binary path so we can launch it using a threaded subprocess
    try:
        app_plist = FoundationPlist.readPlist(os.path.join(app_path, 'Contents', 'Info.plist'))
        binary = app_plist['CFBundleExecutable']
    except:
        NSLog("Failed to get app binary location, cannot launch.")

    app_list =  NSWorkspace.sharedWorkspace().runningApplications()
    # Before launching the app, check to see if it is already running
    app_running = False
    for app in app_list:
        if app_plist['CFBundleIdentifier'] == app.bundleIdentifier():
            app_running = True

    # Only launch the app if it isn't already running
    if not app_running:
        thread = CustomThread(os.path.join(app_path,'Contents', 'MacOS', binary))
        thread.daemon = True
        thread.start()
        time.sleep(1)

    # Bring application to the front as they launch in the background in Netboot for some reason
    NSWorkspace.sharedWorkspace().launchApplication_(app_path)

def get_hardware_info():
    '''Uses system profiler to get hardware info for this machine'''
    cmd = ['/usr/sbin/system_profiler', 'SPHardwareDataType', '-xml']
    proc = subprocess.Popen(cmd, shell=False, bufsize=-1,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (output, unused_error) = proc.communicate()
    try:
        plist = FoundationPlist.readPlistFromString(output)
        # system_profiler xml is an array
        sp_dict = plist[0]
        items = sp_dict['_items']
        sp_hardware_dict = items[0]
        return sp_hardware_dict
    except Exception:
        return {}

def setup_logging():
    syslog = getPlistData('syslog')

    if not syslog:
        return

    # Parse syslog URI
    try:
        uri = urlparse.urlparse(syslog)
        qs = urlparse.parse_qs(uri.query)

        hostname = uri.hostname if uri.hostname else "localhost"
        port = uri.port if uri.port else 514
        socktype = socket.SOCK_STREAM if qs['transport'][0] == 'TCP' else socket.SOCK_DGRAM
        facility = qs['facility'][0] if 'facility' in qs else "local7"
    except:
        NSLog("Failed to parse syslog URI.")

    # Create a syslog handler
    handler = logging.handlers.SysLogHandler(address=(hostname, port),
                                             facility=facility,
                                             socktype=socktype)

    # Configure logging
    formatter = logging.Formatter('%(name)s: %(message)s')
    handler.setFormatter(formatter)
    logging.getLogger("Imagr").addHandler(handler)
    logging.getLogger("Imagr").setLevel("INFO")

def replacePlaceholders(script, target, computer_name=None, keyboard_layout_id=None, keyboard_layout_name=None, language=None, locale=None, timezone=None):
    hardware_info = get_hardware_info()
    placeholders = {
        "{{target_volume}}": target,
        "{{serial_number}}": hardware_info.get('serial_number', 'UNKNOWN'),
        "{{machine_model}}": hardware_info.get('machine_model', 'UNKNOWN'),
    }

    if computer_name:
        placeholders['{{computer_name}}'] = computer_name

    if keyboard_layout_id:
        placeholders['{{keyboard_layout_id}}'] = keyboard_layout_id

    if keyboard_layout_name:
        placeholders['{{keyboard_layout_name}}'] = keyboard_layout_name

    if language:
        placeholders['{{language}}'] = language

    if locale:
        placeholders['{{locale}}'] = locale

    if timezone:
        placeholders['{{timezone}}'] = timezone

    for placeholder, value in placeholders.iteritems():
        script = script.replace(placeholder, str(value))
        
    script = xml.sax.saxutils.unescape(script)
    return script

def mountdmg(dmgpath):
    """
    Attempts to mount the dmg at dmgpath
    and returns a list of mountpoints
    """
    NSLog("Mounting disk image %@", dmgpath)
    mountpoints = []
    dmgname = os.path.basename(dmgpath)
    cmd = ['/usr/bin/hdiutil', 'attach', dmgpath, '-nobrowse', '-plist',
           '-owners', 'on']
    proc = subprocess.Popen(cmd, bufsize=-1,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (pliststr, err) = proc.communicate()
    if proc.returncode:
        print >> sys.stderr, 'Error: "%s" while mounting %s.' % (err, dmgname)
    if pliststr:
        plist = plistlib.readPlistFromString(pliststr)
        for entity in plist['system-entities']:
            if 'mount-point' in entity:
                mountpoints.append(entity['mount-point'])
        NSLog("Mount successful at %@", mountpoints)

    return mountpoints


def unmountdmg(mountpoint):
    """
    Unmounts the dmg at mountpoint
    """
    NSLog("Unmounting disk image at %@", mountpoint)
    proc = subprocess.Popen(['/usr/bin/hdiutil', 'detach', mountpoint],
                            bufsize=-1, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    (unused_output, err) = proc.communicate()
    if proc.returncode:
        print >> sys.stderr, 'Polite unmount failed: %s' % err
        print >> sys.stderr, 'Attempting to force unmount %s' % mountpoint
        # try forcing the unmount
        retcode = subprocess.call(['/usr/bin/hdiutil', 'detach', mountpoint,
                                   '-force'])
        if retcode:
            print >> sys.stderr, 'Failed to unmount %s' % mountpoint
            return False
        else:
            return True
    else:
        return True


def downloadChunks(url, file, progress_method=None, additional_headers=None):
    message = "Downloading %s" % os.path.basename(url)
    try:
        headers = get_url(url, file, message=message, progress_method=progress_method, additional_headers=additional_headers)
    except HTTPError, err:
        NSLog("HTTP Error: %@", err)
        return False, err
    except GurlError, err:
        NSLog("Gurl Error: %@", err)
        return False, err
    else:
        return file, None


def copyFirstBoot(root):
    NSLog("Copying first boot pkg install tools")
    # Create the config plist
    config_plist = {}
    network = True
    retry_count = 10
    config_plist['Network'] = network
    config_plist['RetryCount'] = retry_count
    firstboot_dir = 'usr/local/first-boot'
    if not os.path.exists(os.path.join(root, firstboot_dir)):
        os.makedirs(os.path.join(root, firstboot_dir))
    plistlib.writePlist(config_plist, os.path.join(root, firstboot_dir, 'config.plist'))

    # Copy the LaunchDaemon, LaunchAgent and Log.app to the right places
    script_dir = os.path.dirname(os.path.realpath(__file__))
    launchDaemon_dir = os.path.join(root, 'Library', 'LaunchDaemons')
    if not os.path.exists(launchDaemon_dir):
        os.makedirs(launchDaemon_dir)

    if not os.path.exists(os.path.join(launchDaemon_dir,
    'com.grahamgilbert.first-boot-pkg.plist')):
        shutil.copy(os.path.join(script_dir,
        'com.grahamgilbert.first-boot-pkg.plist'), os.path.join(launchDaemon_dir,
        'com.grahamgilbert.first-boot-pkg.plist'))
        # Set the permisisons
        os.chmod(os.path.join(launchDaemon_dir,
        'com.grahamgilbert.first-boot-pkg.plist'), 0644)
        os.chown(os.path.join(launchDaemon_dir,
        'com.grahamgilbert.first-boot-pkg.plist'), 0, 0)

    launchAgent_dir = os.path.join(root, 'Library', 'LaunchAgents')
    if not os.path.exists(launchAgent_dir):
        os.makedirs(launchAgent_dir)

    if not os.path.exists(os.path.join(launchAgent_dir, 'se.gu.it.LoginLog.plist')):
        shutil.copy(os.path.join(script_dir, 'se.gu.it.LoginLog.plist'),
        os.path.join(launchAgent_dir, 'se.gu.it.LoginLog.plist'))
        # Set the permisisons
        os.chmod(os.path.join(launchAgent_dir, 'se.gu.it.LoginLog.plist'), 0644)
        os.chown(os.path.join(launchAgent_dir, 'se.gu.it.LoginLog.plist'), 0, 0)

    helperTools_dir = os.path.join(root, 'Library', 'PrivilegedHelperTools')
    if not os.path.exists(helperTools_dir):
        os.makedirs(helperTools_dir)

    if not os.path.exists(os.path.join(helperTools_dir, 'LoginLog.app')):
        shutil.copytree(os.path.join(script_dir, 'LoginLog.app'),
        os.path.join(helperTools_dir, 'LoginLog.app'))
        # Set the permisisons
        for root_dir, dirs, files in os.walk(os.path.join(helperTools_dir, 'LoginLog.app')):
          for momo in dirs:
            os.chown(os.path.join(root_dir, momo), 0, 0)
            os.chmod(os.path.join(root_dir, momo), 0755)
          for momo in files:
            os.chown(os.path.join(root_dir, momo), 0, 0)
            os.chmod(os.path.join(root_dir, momo), 0755)

    if not os.path.exists(os.path.join(root, firstboot_dir, 'first-boot')):
        # copy the script
        shutil.copy(os.path.join(script_dir, 'first-boot'), os.path.join(root, firstboot_dir, 'first-boot'))
        # Set the permisisons
        os.chmod(os.path.join(root, firstboot_dir, 'first-boot'), 0755)
        os.chown(os.path.join(root, firstboot_dir, 'first-boot'), 0, 0)
