from setuptools import setup, find_packages

# get install requirements
with open('requirements.txt') as fh:
    install_requires = fh.read().splitlines()

setup(
    name='lpdaac-gedi-subsetter',
    version='0.0.0.1',
    description='Program for using the LP.DAAC GEDI subsetter api for retrieving NASA GEDI data',
    url='https://github.com/tsutterley/lpdaac-gedi-subsetter',
    author='Tyler Sutterley',
    author_email='tsutterl@uw.edu',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Physics',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    keywords='LP.DAAC GEDI laser altimetry subsetting',
    packages=find_packages(),
    scripts=['lpdaac_subset_gedi.py'],
    install_requires=install_requires,
)
