"""
utilities.py
Written by Tyler Sutterley (09/2020)
Download and management utilities for syncing time and auxiliary files

UPDATE HISTORY:
    Written 09/2020
"""
from __future__ import print_function

import sys
import os
import ssl
import shutil
import base64
import inspect
import hashlib
import posixpath
import calendar,time
if sys.version_info[0] == 2:
    from cookielib import CookieJar
    import urllib2
else:
    from http.cookiejar import CookieJar
    import urllib.request as urllib2

#-- PURPOSE: get the MD5 hash value of a file
def get_hash(local):
    """
    Get the MD5 hash value from a local file

    Arguments
    ---------
    local: path to file
    """
    #-- check if local file exists
    if os.access(os.path.expanduser(local),os.F_OK):
        #-- generate checksum hash for local file
        #-- open the local_file in binary read mode
        with open(os.path.expanduser(local), 'rb') as local_buffer:
            return hashlib.md5(local_buffer.read()).hexdigest()
    else:
        return ''

#-- PURPOSE: recursively split a url path
def url_split(s):
    head, tail = posixpath.split(s)
    if head in ('', posixpath.sep):
        return tail,
    return url_split(head) + (tail,)

#-- PURPOSE: returns the Unix timestamp value for a formatted date string
def get_unix_time(time_string, format='%Y-%m-%d %H:%M:%S'):
    """
    Get the Unix timestamp value for a formatted date string

    Arguments
    ---------
    time_string: formatted time string to parse

    Keyword arguments
    -----------------
    format: format for input time string
    """
    try:
        parsed_time = time.strptime(time_string.rstrip(), format)
    except:
        return None
    else:
        return calendar.timegm(parsed_time)

#-- PURPOSE: check internet connection
def check_connection(HOST):
    """
    Check internet connection

    Arguments
    ---------
    HOST: remote http host
    """
    #-- attempt to connect to https host
    try:
        urllib2.urlopen(HOST,timeout=20,context=ssl.SSLContext())
    except urllib2.URLError:
        raise RuntimeError('Check internet connection')
    else:
        return True

#-- PURPOSE: "login" to NASA Earthdata with supplied credentials
def build_opener(username, password, urs='https://urs.earthdata.nasa.gov'):
    """
    build urllib opener for NASA Earthdata with supplied credentials

    Arguments
    ---------
    username: NASA Earthdata username
    password: NASA Earthdata password

    Keyword arguments
    -----------------
    urs: Earthdata login URS 3 host
    """
    #-- https://docs.python.org/3/howto/urllib2.html#id5
    #-- create a password manager
    password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
    #-- Add the username and password for NASA Earthdata Login system
    password_mgr.add_password(None,urs,username,password)
    #-- Create cookie jar for storing cookies. This is used to store and return
    #-- the session cookie given to use by the data server (otherwise will just
    #-- keep sending us back to Earthdata Login to authenticate).
    cookie_jar = CookieJar()
    #-- create "opener" (OpenerDirector instance)
    opener = urllib2.build_opener(
        urllib2.HTTPBasicAuthHandler(password_mgr),
        urllib2.HTTPSHandler(context=ssl.SSLContext()),
        urllib2.HTTPRedirectHandler(),
        urllib2.HTTPCookieProcessor(cookie_jar))
    #-- Now all calls to urllib2.urlopen use our opener.
    urllib2.install_opener(opener)
    #-- All calls to urllib2.urlopen will now use handler
    #-- Make sure not to include the protocol in with the URL, or
    #-- HTTPPasswordMgrWithDefaultRealm will be confused.

#-- PURPOSE: download a file from NASA LP.DAAC https server
def from_lpdaac(remote_file,local_file,username=None,password=None,build=True,
    timeout=None,hash='',chunk=16384,mode=0o775):
    """
    Download a file from NASA LP.DAAC archive server

    Arguments
    ---------
    HOST: remote https host path split as list

    Keyword arguments
    -----------------
    username: NASA Earthdata username
    password: NASA Earthdata password
    build: Build opener
    timeout: timeout in seconds for blocking operations
    local: path to local file
    hash: MD5 hash of local file
    chunk: chunk size for transfer encoding
    mode: permissions mode of output local file

    Returns
    -------
    output: string describing input and output files
    """
    #-- build urllib2 opener and check credentials
    if build:
        #-- build urllib2 opener with credentials
        build_opener(username, password)
    #-- recursively create local directory and change permissions mode
    if not os.access(os.path.dirname(local_file), os.F_OK):
        os.makedirs(os.path.dirname(local_file),mode)
    #-- try downloading from https
    try:
        #-- Create and submit request.
        #-- There are a wide range of exceptions that can be thrown here
        #-- including HTTPError and URLError.
        request = urllib2.Request(remote_file)
        print("Downloading: ", remote_file)
        response = urllib2.urlopen(request, timeout=timeout)
    except:
        raise Exception('Download error from {0}'.format(remote_file))
    else:
        #-- string to print files transferred
        output = '{0} -->\n\t{1}\n'.format(remote_file,local_file)
        #-- copy contents to local file using chunked transfer encoding
        #-- transfer should work properly with ascii and binary formats
        with open(local_file, 'wb') as f:
            shutil.copyfileobj(response, f, chunk)
        #-- change permissions mode
        os.chmod(local_file, mode)
        #-- return the output string
        return output
