#!/usr/bin/env python
u"""
lpdaac_subset_gedi.py
Written by Tyler Sutterley (11/2021)

Program to acquire subset GEDI altimetry datafiles from the LP.DAAC API:
https://wiki.earthdata.nasa.gov/display/EL/How+To+Access+Data+With+Python
https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html
http://www.voidspace.org.uk/python/articles/authentication.shtml#base64

Register with NASA Earthdata Login system:
https://urs.earthdata.nasa.gov

CALLING SEQUENCE:
    python lpdaac_subset_gedi.py -T 2019-04-01T00:00:00 2019-04-30T23:59:59
        -B 40.0 -100 42.0 -96.0 --version 001 --user <username> -V GEDI01_B
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
    Updated 11/2021: use scrolling CMR queries to granule names
        using logging for verbose output
    Updated 08/2021: use NASA CMR system to query for granules
        Use convex hull of polygons to search with CMR system
    Updated 07/2021: set context for multiprocessing to fork child processes
        update regular expression pattern for release 2 of the files
    Updated 05/2021: use try/except for retrieving netrc credentials
    Updated 04/2021: set a default netrc file and check access
        default credentials from environmental variables
    Updated 12/2020: use absolute path for argparse paths
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
import json
import netrc
import getpass
import logging
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

#-- PURPOSE: build string for version queries
def build_version_query(version, desired_pad_length=3):
    #-- check that the version is less than the required
    if (len(str(version)) > desired_pad_length):
        raise Exception('Version string too long: "{0}"'.format(version))
    #-- Strip off any leading zeros
    version = int(version)
    query_params = ""
    while (len(str(version)) <= desired_pad_length):
        padded_version = str(version).zfill(desired_pad_length)
        query_params += '&version={0}'.format(padded_version)
        desired_pad_length -= 1
    #-- return the query parameters
    return query_params

#-- PURPOSE: Select only the desired data files from CMR response
def cmr_filter_json(search_page, form="application/x-hdfeos"):
    #-- check that there are urls for request
    urls = list()
    if (('feed' not in search_page.keys()) or
        ('entry' not in search_page['feed'].keys())):
        return urls
    #-- iterate over references and get cmr location
    for entry in search_page['feed']['entry']:
        #-- find url for format type
        for i,link in enumerate(entry['links']):
            if ('type' in link.keys()) and (link['type'] == form):
                urls.append(entry['links'][i]['href'])
    return urls

#-- PURPOSE: program to acquire subsetted LP.DAAC data
def lpdaac_subset_gedi(DIRECTORY, PRODUCT, VERSION, BBOX=None, POLYGON=None,
    TIME=None, PROCESSES=0, VERBOSE=False, MODE=None):

    #-- create logger
    loglevel = logging.INFO if VERBOSE else logging.CRITICAL
    logging.basicConfig(level=loglevel)

    #-- print query flag
    logging.info("Querying NASA CMR for available granules")
    #-- product and version flags
    product_flag = '?short_name={0}'.format(PRODUCT)
    version_flag = build_version_query(VERSION) if VERSION else ''

    #-- spatially subset data using bounding box or polygon file
    if BBOX:
        #-- if using a bounding box to spatially subset data
        #-- API expects: min_lon,min_lat,max_lon,max_lat
        bounds_flag = '{1:f},{0:f},{3:f},{2:f}'.format(*BBOX)
        spatial_flag = '&bounding_box={0}'.format(bounds_flag)
        logging.info("Spatial bounds: {0}".format(bounds_flag))
    elif POLYGON:
        #-- read shapefile or kml/kmz file
        _,fileExtension = os.path.splitext(POLYGON)
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
        #-- calculate the convex hull of the MultiPolygon object for subsetting
        #-- the CMR api requires polygons to be in counter-clockwise order
        qhull = mpoly.convex_hull()
        #-- get exterior coordinates of complex hull
        X,Y = qhull.xy()
        #-- coordinate order for polygon flag is lon1,lat1,lon2,lat2,...
        polygon_flag = ','.join(['{0:f},{1:f}'.format(x,y) for x,y in zip(X,Y)])
        spatial_flag = '&polygon[]={0}'.format(polygon_flag)
    else:
        #-- do not spatially subset data
        spatial_flag = ''

    #-- if using time start and end to temporally subset data
    if TIME:
        #-- verify that start and end times are in ISO format
        start_time = dateutil.parser.parse(TIME[0]).isoformat()
        end_time = dateutil.parser.parse(TIME[1]).isoformat()
        temporal_flag = '&temporal={0},{1}'.format(start_time, end_time)
    else:
        temporal_flag = ''

    #-- get dictionary of granules for temporal and spatial subset
    HOST=posixpath.join('https://cmr.earthdata.nasa.gov','search','granules.json')
    page_size = 100
    granules = []
    cmr_scroll_id = None
    while True:
        #-- flags for page size
        size_flag = '&page_size={0:d}'.format(page_size)
        #-- url for page
        cmr_query_url = ''.join([HOST,product_flag,'&provider=LPDAAC_ECS',
            '&sort_key[]=start_date','&sort_key[]=producer_granule_id',
            '&scroll=true',version_flag,spatial_flag,temporal_flag,size_flag])
        request = subsetting_tools.utilities.urllib2.Request(cmr_query_url)
        if cmr_scroll_id:
            request.add_header('cmr-scroll-id', cmr_scroll_id)
        response=subsetting_tools.utilities.urllib2.urlopen(request, timeout=20)
        if not cmr_scroll_id:
            # Python 2 and 3 have different case for the http headers
            headers = {k.lower(): v for k, v in dict(response.info()).items()}
            cmr_scroll_id = headers['cmr-scroll-id']
            hits = int(headers['cmr-hits'])
        #-- parse the json response
        search_page = json.loads(response.read())
        url_scroll_results = cmr_filter_json(search_page)
        if not url_scroll_results:
            break
        granules.extend(url_scroll_results)

    #-- print number of files found for spatial and temporal query
    logging.info("Query returned {} files".format(len(granules)))

    #-- sync in series if PROCESSES = 0
    if (PROCESSES == 0):
        #-- retrieve each GEDI file from LP.DAAC server
        for granule in granules:
            #-- local version of file
            args = subsetting_tools.utilities.url_split(granule)
            local_file = os.path.join(DIRECTORY,args[-2],args[-1])
            xml = '{0}.xml'.format(granule)
            if not subsetting_tools.utilities.compare_checksums(xml,local_file):
                #-- get remote file
                out = subsetting_tools.utilities.from_lpdaac(granule, local_file,
                    build=False, verbose=VERBOSE, mode=MODE)
                #-- print the output string
                logging.info(out)
    else:
        logging.info('Syncing in parallel with {0:d} processes'.format(PROCESSES))
        #-- set multiprocessing start method
        ctx = mp.get_context("fork")
        #-- sync in parallel with multiprocessing Pool
        pool = ctx.Pool(processes=PROCESSES)
        #-- retrieve each GEDI file from LP.DAAC server
        output = []
        for granule in granules:
            #-- local version of file
            args = subsetting_tools.utilities.url_split(granule)
            local_file = os.path.join(DIRECTORY,args[-2],args[-1])
            output.append(pool.apply_async(multiprocess_sync,
                args=(granule,local_file,MODE)))
        #-- start multiprocessing jobs
        #-- close the pool
        #-- prevents more tasks from being submitted to the pool
        pool.close()
        #-- exit the completed processes
        pool.join()
        #-- print the output string
        for out in output:
            logging.info(out.get())

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
            logging.critical('process id {0:d} failed'.format(os.getpid()))
            logging.error(traceback.format_exc())
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
        type=lambda p: os.path.abspath(os.path.expanduser(p)),
        default=os.getcwd(),
        help='Working data directory')
    parser.add_argument('--user','-U',
        type=str, default=os.environ.get('EARTHDATA_USERNAME'),
        help='Username for NASA Earthdata Login')
    parser.add_argument('--netrc','-N',
        type=lambda p: os.path.abspath(os.path.expanduser(p)),
        default=os.path.join(os.path.expanduser('~'),'.netrc'),
        help='Path to .netrc file for authentication')
    parser.add_argument('--np','-P',
        metavar='PROCESSES', type=int, default=0,
        help='Number of processes to use in file downloads')
    parser.add_argument('--version','-v',
        type=str, default='002',
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
    URS = 'urs.earthdata.nasa.gov'
    #-- get authentication
    try:
        args.user,_,PASSWORD = netrc.netrc(args.netrc).authenticators(URS)
    except:
        #-- check that NASA Earthdata credentials were entered
        if not args.user:
            prompt = 'Username for {0}: '.format(URS)
            args.user = builtins.input(prompt)
        #-- enter password securely from command-line
        prompt = 'Password for {0}@{1}: '.format(args.user,URS)
        PASSWORD = getpass.getpass(prompt)
    #-- build an opener for LP.DAAC
    opener = subsetting_tools.utilities.build_opener(args.user, PASSWORD)

    #-- recursively create directory if presently non-existent
    if not os.access(args.directory, os.F_OK):
        os.makedirs(args.directory, args.mode)

    #-- check internet connection before attempting to run program
    if subsetting_tools.utilities.check_connection('https://lpdaac.usgs.gov'):
        #-- for each GEDI product
        for p in args.product:
            #-- run program for product
            lpdaac_subset_gedi(args.directory,p,args.version,BBOX=args.bbox,
                POLYGON=args.polygon,TIME=args.time,PROCESSES=args.np,
                VERBOSE=args.verbose,MODE=args.mode)

#-- run main program
if __name__ == '__main__':
    main(sys.argv)
