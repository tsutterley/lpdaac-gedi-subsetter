#!/usr/bin/env python
u"""
utilities.py
Written by Tyler Sutterley (07/2021)
Download and management utilities for syncing files

UPDATE HISTORY:
    Updated 07/2021: return Earthdata opener from build function
    Updated 03/2021: added sha1 option for retrieving file hashes
    Updated 12/2020: added file object keyword for downloads if verbose
        get_hash can accept file-like (e.g. BytesIO) objects
    Updated 09/2020: generalize build opener function for different instances
    Written 09/2020
"""
from __future__ import print_function

import sys
import os
import io
import ssl
import netrc
import shutil
import base64
import hashlib
import posixpath
import lxml.etree
import calendar,time
if sys.version_info[0] == 2:
    from cookielib import CookieJar
    import urllib2
else:
    from http.cookiejar import CookieJar
    import urllib.request as urllib2

#-- PURPOSE: get the hash value of a file
def get_hash(local, algorithm='MD5'):
    """
    Get the hash value from a local file or BytesIO object

    Arguments
    ---------
    local: BytesIO object or path to file

    Keyword Arguments
    -----------------
    algorithm: hashing algorithm for checksum validation
        MD5: Message Digest
        sha1: Secure Hash Algorithm
    """
    #-- check if open file object or if local file exists
    if isinstance(local, io.IOBase):
        if (algorithm == 'MD5'):
            return hashlib.md5(local.getvalue()).hexdigest()
        elif (algorithm == 'sha1'):
            return hashlib.sha1(local.getvalue()).hexdigest()
    elif os.access(os.path.expanduser(local),os.F_OK):
        #-- generate checksum hash for local file
        #-- open the local_file in binary read mode
        with open(os.path.expanduser(local), 'rb') as local_buffer:
            #-- generate checksum hash for a given type
            if (algorithm == 'MD5'):
                return hashlib.md5(local_buffer.read()).hexdigest()
            elif (algorithm == 'sha1'):
                return hashlib.sha1(local_buffer.read()).hexdigest()
    else:
        return ''

#-- PURPOSE: recursively split a url path
def url_split(s):
    """
    Recursively split a url path into a list

    Arguments
    ---------
    s: url string
    """
    head, tail = posixpath.split(s)
    if head in ('http:','https:'):
        return s,
    elif head in ('', posixpath.sep):
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
    except (TypeError, ValueError):
        return None
    else:
        return calendar.timegm(parsed_time)

#-- PURPOSE: rounds a number to an even number less than or equal to original
def even(value):
    """
    Rounds a number to an even number less than or equal to original

    Arguments
    ---------
    value: number to be rounded
    """
    return 2*int(value//2)

#-- PURPOSE: make a copy of a file with all system information
def copy(source, destination, verbose=False, move=False):
    """
    Copy or move a file with all system information

    Arguments
    ---------
    source: source file
    destination: copied destination file

    Keyword arguments
    -----------------
    verbose: print file transfer information
    move: remove the source file
    """
    source = os.path.abspath(os.path.expanduser(source))
    destination = os.path.abspath(os.path.expanduser(destination))
    print('{0} -->\n\t{1}'.format(source,destination)) if verbose else None
    shutil.copyfile(source, destination)
    shutil.copystat(source, destination)
    if move:
        os.remove(source)

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
def build_opener(username, password, context=ssl.SSLContext(),
    password_manager=True, get_ca_certs=False, redirect=True,
    authorization_header=False, urs='https://urs.earthdata.nasa.gov'):
    """
    build urllib opener for NASA Earthdata with supplied credentials

    Arguments
    ---------
    username: NASA Earthdata username
    password: NASA Earthdata password

    Keyword arguments
    -----------------
    context: SSL context for opener object
    password_manager: create password manager context using default realm
    get_ca_certs: get list of loaded “certification authority” certificates
    redirect: create redirect handler object
    authorization_header: add base64 encoded authorization header to opener
    urs: Earthdata login URS 3 host
    """
    #-- https://docs.python.org/3/howto/urllib2.html#id5
    handler = []
    #-- create a password manager
    if password_manager:
        password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        #-- Add the username and password for NASA Earthdata Login system
        password_mgr.add_password(None,urs,username,password)
        handler.append(urllib2.HTTPBasicAuthHandler(password_mgr))
    #-- Create cookie jar for storing cookies. This is used to store and return
    #-- the session cookie given to use by the data server (otherwise will just
    #-- keep sending us back to Earthdata Login to authenticate).
    cookie_jar = CookieJar()
    handler.append(urllib2.HTTPCookieProcessor(cookie_jar))
    #-- SSL context handler
    if get_ca_certs:
        context.get_ca_certs()
    handler.append(urllib2.HTTPSHandler(context=context))
    #-- redirect handler
    if redirect:
        handler.append(urllib2.HTTPRedirectHandler())
    #-- create "opener" (OpenerDirector instance)
    opener = urllib2.build_opener(*handler)
    #-- Encode username/password for request authorization headers
    #-- add Authorization header to opener
    if authorization_header:
        b64 = base64.b64encode('{0}:{1}'.format(username,password).encode())
        opener.addheaders = [("Authorization","Basic {0}".format(b64.decode()))]
    #-- Now all calls to urllib2.urlopen use our opener.
    urllib2.install_opener(opener)
    #-- All calls to urllib2.urlopen will now use handler
    #-- Make sure not to include the protocol in with the URL, or
    #-- HTTPPasswordMgrWithDefaultRealm will be confused.
    return opener

#-- PURPOSE: download a file from NASA LP.DAAC https server
def from_lpdaac(remote_file,local_file,username=None,password=None,build=True,
    timeout=None,chunk=16384,verbose=False,fid=sys.stdout,mode=0o775):
    """
    Download a file from NASA LP.DAAC archive server

    Arguments
    ---------
    remote_file: remote file path
    local_file: local file path

    Keyword arguments
    -----------------
    username: NASA Earthdata username
    password: NASA Earthdata password
    build: Build opener
    timeout: timeout in seconds for blocking operations
    chunk: chunk size for transfer encoding
    verbose: verbose output of download
    fid: open file object to print if verbose
    mode: permissions mode of output local file

    Returns
    -------
    output: string describing input and output files
    """
    #-- use netrc credentials
    if build and not (username or password):
        urs = 'urs.earthdata.nasa.gov'
        username,_,password = netrc.netrc().authenticators(urs)
    #-- build urllib2 opener and check credentials
    if build:
        #-- build urllib2 opener with credentials
        build_opener(username, password)
    #-- convert to absolute path
    local_file = os.path.abspath(local_file)
    #-- recursively create local directory and change permissions mode
    if not os.access(os.path.dirname(local_file), os.F_OK):
        os.makedirs(os.path.dirname(local_file),mode)
    #-- try downloading from https
    try:
        #-- Create and submit request.
        #-- There are a wide range of exceptions that can be thrown here
        #-- including HTTPError and URLError.
        request = urllib2.Request(remote_file)
        response = urllib2.urlopen(request, timeout=timeout)
        #-- string to print files transferred
        output = '{0} -->\n\t{1}\n'.format(remote_file,local_file)
        print(output, file=fid) if verbose else None
    except:
        raise Exception('Download error from {0}'.format(remote_file))
    else:
        #-- copy contents to local file using chunked transfer encoding
        #-- transfer should work properly with ascii and binary formats
        with open(local_file, 'wb') as f:
            shutil.copyfileobj(response, f, chunk)
        #-- change permissions mode
        os.chmod(local_file, mode)
        #-- return the output string
        return output

#-- PURPOSE: compare MD5 checksums from xml file and local file
def compare_checksums(remote_xml,local_file,username=None,password=None,
    build=False,timeout=None):
    """
    Compare MD5 checksums from xml file and local file

    Arguments
    ---------
    remote_xml: remote XML file path
    local_file: local file path

    Keyword arguments
    -----------------
    username: NASA Earthdata username
    password: NASA Earthdata password
    build: Build opener
    timeout: timeout in seconds for blocking operations

    Returns
    -------
    output: results of comparison between checksums
    """
    #-- use netrc credentials
    if build and not (username or password):
        urs = 'urs.earthdata.nasa.gov'
        username,_,password = netrc.netrc().authenticators(urs)
    #-- build urllib2 opener and check credentials
    if build:
        #-- build urllib2 opener with credentials
        build_opener(username, password)
    #-- try reading xml file from https
    try:
        request = urllib2.Request(remote_xml)
        response = urllib2.urlopen(request,timeout=timeout)
    except:
        raise Exception('XML download error: {0}'.format(remote_xml))
    else:
        #-- get MDF5 hash of remote file
        tree = lxml.etree.parse(response,lxml.etree.XMLParser())
        remote_hash, = tree.xpath('//DataFileContainer/Checksum/text()')
        #-- get MDF5 hash of local file
        local_hash = get_hash(local_file)
        #-- compare checksums and return result
        return (local_hash == remote_hash)
