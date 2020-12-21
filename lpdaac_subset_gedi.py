#!/usr/bin/env python
u"""
lpdaac_subset_gedi.py
Written by Tyler Sutterley (10/2020)

Program to acquire subset GEDI altimetry datafiles from the LP.DAAC API:
https://wiki.earthdata.nasa.gov/display/EL/How+To+Access+Data+With+Python
https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html
http://www.voidspace.org.uk/python/articles/authentication.shtml#base64

Register with NASA Earthdata Login system:
https://urs.earthdata.nasa.gov

CALLING SEQUENCE:
    python lpdaac_subset_gedi.py -T 2019-04-01T00:00:00 2019-04-30T23:59:59
        -B 42.0 -100 40.0 -96.0 --version 001 --user <username> -V GEDI01_B
    where <username> is your NASA Earthdata username

INPUTS:
    GEDI01_B: Level 1B Geolocated Waveforms
    GEDI02_A: Level 2A Elevation and Height Metrics
    GEDI02_B: Level 2B Canopy Cover and Vertical Profile Metrics

COMMAND LINE OPTIONS:
    -h, --help: list the command line options
    -D X, --directory X: working data directory
    -U X, --user X: username for NASA Earthdata Login
    -N X, --netrc X: path to .netrc file for alternative authentication
    -P X, --np X: Number of processes to use in file downloads
    -v X, --version: version of the dataset to use
    -B X, --bbox X: Bounding box [lat_min,lon_min,lat_max,lon_max]
    -p X, --polygon X: Georeferenced file containing a set of polygons
    -T X, --time X: Time range [start_time,end_time]
    -M X, --mode X: Local permissions mode of the files processed
    -V, --verbose: Verbose output of processing

PYTHON DEPENDENCIES:
    future: Compatibility layer between Python 2 and Python 3
        http://python-future.org/
    numpy: Scientific Computing Tools For Python
        https://numpy.org
        https://numpy.org/doc/stable/user/numpy-for-matlab-users.html
    fiona: Python wrapper for vector data access functions from the OGR library
        https://fiona.readthedocs.io/en/latest/manual.html
    geopandas: Python tools for geographic data
        http://geopandas.readthedocs.io/
    shapely: PostGIS-ish operations outside a database context for Python
        http://toblerity.org/shapely/index.html
    pyproj: Python interface to PROJ library
        https://pypi.org/project/pyproj/
    lxml: processing XML and HTML in Python
        https://pypi.python.org/pypi/lxml
    dateutil: powerful extensions to datetime
        https://dateutil.readthedocs.io/en/stable/

PROGRAM DEPENDENCIES:
    polygon.py: Reads polygons from GeoJSON, kml/kmz or ESRI shapefile files
    utilities.py: Download and management utilities for syncing files

UPDATE HISTORY:
    Updated 10/2020: added polygon option to use bounds from georeferenced file
    Updated 09/2020: added more verbose flags to show progress
        using argparse instead of getopt to set command line parameters
        add argparse type for tilde expansion of files and directories
    Written 09/2020
"""
from __future__ import print_function
import future.standard_library

import sys
import os
import re
import ssl
import json
import netrc
import getpass
import datetime
import builtins
import argparse
import posixpath
import traceback
import dateutil.rrule
import dateutil.parser
import multiprocessing as mp
import subsetting_tools.polygon
import subsetting_tools.utilities
with future.standard_library.hooks():
    import urllib.request

#-- PURPOSE: program to acquire subsetted LP.DAAC data
def lpdaac_subset_gedi(DIRECTORY, PRODUCT, VERSION, BBOX=None, POLYGON=None,
    TIME=None, PROCESSES=0, VERBOSE=False, MODE=None):

    #-- print query flag
    print("Querying LP-DAAC for available granules") if VERBOSE else None
    #-- product and version flags
    product_flag = '?product={0}'.format(PRODUCT)
    version_flag = '&version={0}'.format(VERSION) if VERSION else ''

    #-- spatially subset data using bounding box or polygon file
    if BBOX:
        #-- if using a bounding box to spatially subset data
        #-- API expects: min_lat,min_lon,max_lat,max_lon
        bounds_flag = '&bbox={0:f},{1:f},{2:f},{3:f}'.format(*BBOX)
        if VERBOSE:
            print("Spatial bounds: {1:f},{0:f},{3:f},{2:f}".format(*BBOX))
    elif POLYGON:
        #-- read shapefile or kml/kmz file
        fileBasename,fileExtension = os.path.splitext(POLYGON)
        #-- extract file name and subsetter indices lists
        match_object = re.match(r'(.*?)(\[(.*?)\])?$',POLYGON)
        f = os.path.expanduser(match_object.group(1))
        #-- read specific variables of interest
        v = match_object.group(3).split(',') if match_object.group(2) else None
        #-- get MultiPolygon object from input spatial file
        if fileExtension in ('.shp','.zip'):
            #-- if reading a shapefile or a zipped directory with a shapefile
            ZIP = (fileExtension == '.zip')
            mpoly=subsetting_tools.polygon().from_shapefile(f,variables=v,zip=ZIP)
        elif fileExtension in ('.kml','.kmz'):
            #-- if reading a keyhole markup language (can be compressed kmz)
            KMZ = (fileExtension == '.kmz')
            mpoly=subsetting_tools.polygon().from_kml(f,variables=v,kmz=KMZ)
        elif fileExtension in ('.json','.geojson'):
            #-- if reading a GeoJSON file
            mpoly=subsetting_tools.polygon().from_geojson(f,variables=v)
        else:
            raise IOError('Unlisted polygon type ({0})'.format(fileExtension))
        #-- calculate the bounds of the MultiPolygon object
        #-- Polygon object bounds: min_lon,min_lat,max_lon,max_lat
        #-- API expects: min_lat,min_lon,max_lat,max_lon
        bounds_flag = '&bbox={1:f},{0:f},{3:f},{2:f}'.format(*mpoly.bounds)
        if VERBOSE:
            print("Polygon bounds: {1:f},{0:f},{3:f},{2:f}".format(*mpoly.bounds))
    else:
        #-- do not spatially subset data
        bounds_flag = ''

    #-- remote https server for page of LP.DAAC Data
    HOST=posixpath.join('https://lpdaacsvc.cr.usgs.gov','services','gedifinder')
    remote_url=''.join([HOST,product_flag,version_flag,bounds_flag])
    #-- Create and submit request. There are a wide range of exceptions
    #-- that can be thrown here, including HTTPError and URLError.
    request=urllib.request.Request(remote_url)
    response=json.load(urllib.request.urlopen(request,context=ssl.SSLContext()))

    #-- if using time start and end to temporally subset data
    if TIME:
        #-- create a list of times to parse
        days = dateutil.rrule.rrule(dateutil.rrule.DAILY,
            dtstart=dateutil.parser.parse(TIME[0]),
            until=dateutil.parser.parse(TIME[1]))
        #-- create a regular expression pattern for days of the year
        pattern = r'|'.join(datetime.datetime.strftime(t,'%Y%j') for t in days)
        #-- complete regular expression pattern for reducing to time
        args = (PRODUCT,pattern)
        rx = re.compile((r'({0})_({1})(\d{{2}})(\d{{2}})(\d{{2}})_O(\d{{5}})_'
            r'T(\d{{5}})_(\d{{2}})_(\d{{3}})_(\d{{2}})\.h5').format(*args))
        #-- reduce list to times of interest
        file_list = sorted([f for f in response['data'] if rx.search(f)])
    else:
        file_list = sorted(response['data'])
    #-- print number of files found for spatial and temporal query
    print("Query returned {} files".format(len(file_list))) if VERBOSE else None

    #-- sync in series if PROCESSES = 0
    if (PROCESSES == 0):
        #-- retrieve each GEDI file from LP.DAAC server
        for i,remote_file in enumerate(file_list):
            #-- local version of file
            args = subsetting_tools.utilities.url_split(remote_file)
            local_file = os.path.join(DIRECTORY,args[-2],args[-1])
            xml = '{0}.xml'.format(remote_file)
            if not subsetting_tools.utilities.compare_checksums(xml,local_file):
                #-- get remote file
                subsetting_tools.utilities.from_lpdaac(remote_file, local_file,
                    build=False, verbose=VERBOSE, mode=MODE)
    else:
        if VERBOSE:
            print('Syncing in parallel with {0:d} processes'.format(PROCESSES))
        #-- sync in parallel with multiprocessing Pool
        pool = mp.Pool(processes=PROCESSES)
        #-- retrieve each GEDI file from LP.DAAC server
        output = []
        for i,remote_file in enumerate(file_list):
            #-- local version of file
            args = subsetting_tools.utilities.url_split(remote_file)
            local_file = os.path.join(DIRECTORY,args[-2],args[-1])
            output.append(pool.apply_async(multiprocess_sync,
                args=(remote_file,local_file,MODE)))
        #-- start multiprocessing jobs
        #-- close the pool
        #-- prevents more tasks from being submitted to the pool
        pool.close()
        #-- exit the completed processes
        pool.join()
        #-- print the output string
        for out in output:
            print(out.get()) if VERBOSE else None

#-- PURPOSE: wrapper for running the sync program in multiprocessing mode
def multiprocess_sync(remote_file, local_file, MODE):
    remote_xml = '{0}.xml'.format(remote_file)
    if not subsetting_tools.utilities.compare_checksums(remote_xml,local_file):
        try:
            output = subsetting_tools.utilities.from_lpdaac(remote_file,
                local_file, build=False, verbose=False, mode=MODE)
        except:
            #-- if there has been an error exception
            #-- print the type, value, and stack trace of the
            #-- current exception being handled
            print('process id {0:d} failed'.format(os.getpid()))
            traceback.print_exc()
        else:
            return output

#-- Main program that calls lpdaac_subset_gedi()
def main(argv):

    #-- account for a bug in argparse that misinterprets negative arguments
    #-- preserves backwards compatibility of argparse for prior python versions
    for i, arg in enumerate(argv):
        if (arg[0] == '-') and arg[1].isdigit(): argv[i] = ' ' + arg

    #-- Products for the LP.DAAC subsetter
    PRODUCTS = {}
    PRODUCTS['GEDI01_B'] = 'Level 1B Geolocated Waveforms'
    PRODUCTS['GEDI02_A'] = 'Level 2A Elevation and Height Metrics'
    PRODUCTS['GEDI02_B'] = 'Level 2B Canopy Cover and Vertical Profile Metrics'
    #-- Read the system arguments listed after the program
    parser = argparse.ArgumentParser()
    parser.add_argument('product',
        metavar='PRODUCT', type=str, nargs='+', choices=PRODUCTS.keys(),
        help='GEDI Product')
    parser.add_argument('--directory','-D',
        type=os.path.expanduser, default=os.getcwd(),
        help='Working data directory')
    parser.add_argument('--user','-U',
        type=str, default='',
        help='Username for NASA Earthdata Login')
    parser.add_argument('--netrc','-N',
        type=os.path.expanduser, default='',
        help='Path to .netrc file for authentication')
    parser.add_argument('--np','-P',
        metavar='PROCESSES', type=int, default=0,
        help='Number of processes to use in file downloads')
    parser.add_argument('--version','-v',
        type=str, default='001',
        help='Version of the dataset to use')
    parser.add_argument('--bbox','-B',
        type=float, nargs=4, metavar=('lat_min','lon_min','lat_max','lon_max'),
        help='Bounding box')
    parser.add_argument('--polygon','-p',
        type=os.path.expanduser,
        help='Georeferenced file containing a set of polygons')
    parser.add_argument('--time','-T',
        type=str, nargs=2, metavar=('start_time','end_time'),
        help='Time range')
    parser.add_argument('--verbose','-V',
        default=False, action='store_true',
            help='Verbose output of run')
    parser.add_argument('--mode','-M',
        type=lambda x: int(x,base=8), default=0o775,
        help='Permissions mode of output files')
    args = parser.parse_args()

    #-- NASA Earthdata hostname
    HOST = 'urs.earthdata.nasa.gov'
    #-- get authentication
    if not args.user and not args.netrc:
        #-- check that NASA Earthdata credentials were entered
        USER = builtins.input('Username for {0}: '.format(HOST))
        #-- enter password securely from command-line
        PASSWORD = getpass.getpass('Password for {0}@{1}: '.format(USER,HOST))
    elif args.netrc:
        USER,LOGIN,PASSWORD = netrc.netrc(args.netrc).authenticators(HOST)
    else:
        #-- enter password securely from command-line
        USER = args.user
        PASSWORD = getpass.getpass('Password for {0}@{1}: '.format(USER,HOST))
    #-- build an opener for LP.DAAC
    subsetting_tools.utilities.build_opener(USER, PASSWORD)

    #-- recursively create directory if presently non-existent
    if not os.access(args.directory, os.F_OK):
        os.makedirs(args.directory, args.mode)

    #-- check internet connection before attempting to run program
    if subsetting_tools.utilities.check_connection('https://lpdaac.usgs.gov'):
        #-- check that each data product entered was correctly typed
        for p in args.product:
            #-- run program for product
            lpdaac_subset_gedi(args.directory,p,args.version,BBOX=args.bbox,
                POLYGON=args.polygon,TIME=args.time,PROCESSES=args.np,
                VERBOSE=args.verbose,MODE=args.mode)

#-- run main program
if __name__ == '__main__':
    main(sys.argv)
