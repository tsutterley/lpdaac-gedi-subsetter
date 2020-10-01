#!/usr/bin/env python
u"""
test_download.py (08/2020)
"""
import os
import pytest
import inspect
import warnings
import subsetting_tools.utilities

#-- current file path
filename = inspect.getframeinfo(inspect.currentframe()).filename
filepath = os.path.dirname(os.path.abspath(filename))

#-- parametrize remote files
remote_files = []
# remote_files.append(('https://e4ftl01.cr.usgs.gov/GEDI/GEDI01_B.001/2019.04.18/'
#     'GEDI01_B_2019108002011_O01959_T03909_02_003_01.h5'))
# remote_files.append(('https://e4ftl01.cr.usgs.gov/GEDI/GEDI02_A.001/2019.04.18/'
#     'GEDI02_A_2019108002011_O01959_T03909_02_001_01.h5'))
remote_files.append(('https://e4ftl01.cr.usgs.gov/GEDI/GEDI02_B.001/2019.04.18/'
    'GEDI02_B_2019108002011_O01959_T03909_02_001_01.h5'))
@pytest.mark.parametrize("remote_file", remote_files)
#-- PURPOSE: Download GEDI files from LP.DAAC and verify checksums
def test_download(username,password,remote_file):
    args = subsetting_tools.utilities.url_split(remote_file)
    local_file = os.path.join(filepath,args[-2],args[-1])
    output = subsetting_tools.utilities.from_lpdaac(remote_file,local_file,
        username=username,password=password,build=True)
    assert output
    #-- compare checksums between remote xml file and local file
    remote_xml = '{0}.xml'.format(remote_file)
    assert subsetting_tools.utilities.compare_checksums(remote_xml,local_file)
