lpdaac-gedi-subsetter
=====================

[![Language](https://img.shields.io/badge/python-v3.7-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/tsutterley/lpdaac-gedi-subsetter/blob/main/LICENSE)

#### Program for using the LP.DAAC subsetter api for retrieving [NASA/UMD GEDI](https://gedi.umd.edu/) data

- [NASA Earthdata Login system](https://urs.earthdata.nasa.gov)  
- [How to Access Data with Python](https://wiki.earthdata.nasa.gov/display/EL/How+To+Access+Data+With+Python)  
- [NASA Earthdata CMR API Documentation](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html)  

### Calling Sequence
```bash
python lpdaac_subset_gedi.py -T 2019-04-01T00:00:00 2019-04-30T23:59:59 \
	-B 42.0 -100 40.0 -96.0 --version 001 --user <username> -V GEDI02_A
```

#### Products
- GEDI01_B: Level 1B Geolocated Waveforms
- GEDI02_A: Level 2A Elevation and Height Metrics
- GEDI02_B: Level 2B Canopy Cover and Vertical Profile Metrics

#### Options
    `-h`, `--help`: list the command line options  
    `-D X`, `--directory=X`: working data directory  
    `-U X`, `--user=X:` username for NASA Earthdata Login  
    `-N X`, `--netrc=X`: Path to .netrc file for authentication  
    `-P X`, `--np=X`: Number of parallel processes to use in file downloads
    `-v X`, `--version=X`: version of the dataset to use  
    `-B X`, `--bbox=X`: Bounding box (min_lat,min_lon,max_lat,max_lon)  
    `-T X`, `--time=X`: Time range (start_time, end_time)  
    `-V`, `--verbose`: Verbose output of run  
    `-M X`, `--mode=X`: Local permissions mode of output files  

#### Dependencies
- [future: Compatibility layer between Python 2 and Python 3](http://python-future.org/)  
- [lxml: processing XML and HTML in Python](https://pypi.python.org/pypi/lxml)  
- [dateutil: powerful extensions to datetime](https://dateutil.readthedocs.io/en/stable/)

#### Download
The program homepage is:   
https://github.com/tsutterley/lpdaac-gedi-subsetter    
A zip archive of the latest version is available directly at:    
https://github.com/tsutterley/lpdaac-gedi-subsetter/archive/main.zip  

#### Disclaimer  
This program is not sponsored or maintained by the Universities Space Research Association (USRA), the Land Processes Distributed Active Archive Center (LP.DAAC) or NASA.  It is provided here for your convenience but _with no guarantees whatsoever_.
