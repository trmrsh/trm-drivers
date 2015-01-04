#!/usr/bin/env python

"""
This sub-module encapsulates the global variables that are difficult to avoid
with GUIs.  Those in CAPITALS are meant to be immutable; lowercase ones get
updated. I was finding that I was using some variables as very thinly disguised
globals, and decided to bite the bullet. This allows the many variables that
need to be accessed from many discrete places to be wrapped up in a recognisable
namespace.

The meaning of the globals is as follows (uppercase)::

COL   : colours
DAY   : number of seconds in a day
EFAC  : ratio FWHM/sigma for a gaussian
EPH0  : zeropoint for pyephem
EXTINCTION : extinction, mags/airmass
HTTP_PATH_GET         : getting something string (ATC servers)
HTTP_PATH_EXEC        : for executing commands (ATC servers)
HTTP_PATH_CONFIG      : directory on server containing template applications
HTTP_SEARCH_ATTR_NAME : attribute name to search for when getting applications
MJD0  : zeropoint of MJD
SKY   : sky brightenesses
TINS  : Telescop/instrument data
UNIX0 : UNIX time zeropoint
DEFAULT_FONT : standard font (set in drivers)
MENU_FONT    : font for menus (set in drivers)
ENTRY_FONT   : font for data entry fields and mutable fields

and lowercase (all set = None to start with)::

astro   : astronomical information
clog    : command log widget. Used to report actions and results
count   : count & S/N information widget
cpars   : dictionary of configuration parameters
fpslide : focal plane slide widget
info    : information widget
ipars   : instrument parameters widget (windows sizes etc)
observe : widget of observing commands
rlog    : response log widget. Used to report server responses
rpars   : run parameter widget
setup   : setup widget
wheel   : filter wheel controller
star_filter : filter at last press of 'Start'
lakeshore : connection to Lakeshore CCD temperature
logfile : file to log usdriver messages
"""

from __future__ import print_function

import datetime
import Queue

# Ratio of FWHM/sigma for a gaussian
EFAC = 2.3548

# Zeropoints (days) of MJD, unix time and ephem,
# number of seconds in a day
MJD0  = datetime.date(1858,11,17).toordinal()
UNIX0 = datetime.date(1970,1,1).toordinal()
EPH0  = datetime.date(1899,12,31).toordinal() + 0.5
DAY   = 86400.

# FIFO Queue for retrieving exceptions from
# threaded operations
FIFO = Queue.Queue()

# ATC server stuff
HTTP_PATH_GET         = 'get'
HTTP_PATH_EXEC        = 'exec'
HTTP_PATH_CONFIG      = 'config'
HTTP_SEARCH_ATTR_NAME = 'filename'

# Colours
COL = {\
    'main' :     '#d0d0ff', # Colour for the surrounds
    'text' :     '#000050', # Text colour
    'debug' :    '#a0a0ff', # Text background for debug messages
    'warn' :     '#f0c050', # Text background for warnings
    'error' :    '#ffa0a0', # Text background for errors
    'critical' : '#ff0000', # Text background for disasters
    'start' :    '#00e000', # Start / Success button colour when enabled
    'stop' :     '#ff5050', # Stop / Failure button colour when enabled
    'startD' :   '#d0e0d0', # Start / Success button colour when disabled
    'stopD' :    '#ffe0e0', # Stop / Failure button colour when disabled
    'log' :      '#e0d4ff', # Logger windows
    }

# Telescope / instrument info. Most of this is do with estimating count rates
TINS = {\
    'TNO-USPEC' : {\
        'latitude'   : '18 34',   # latitude DMS, North positive
        'longitude'  : '98 28',   # longitude DMS, East positive
        'elevation'  : 2457.,     # Elevation above sea level, metres
        'app'        : 'tno.xml', # Application for the telescope
        'plateScale' : 0.452,     # Arcsecs/unbinned pixel
        'zerop'      : {\
            'u' : 22.29, # update 06/11/13
            'g' : 25.20,
            'r' : 24.96,
            'i' : 24.64,
            'z' : 23.76
            }
        },
    }

# Sky brightness, mags/sq-arsec
SKY = {\
    'd' : {'u' : 22.4, 'g' : 22.2, 'r' : 21.4, 'i' : 20.7, 'z' : 20.3},
    'g' : {'u' : 21.4, 'g' : 21.2, 'r' : 20.4, 'i' : 20.1, 'z' : 19.9},
    'b' : {'u' : 18.4, 'g' : 18.2, 'r' : 17.4, 'i' : 17.9, 'z' : 18.3},
    }

# Extinction per unit airmass
EXTINCTION = {'u' : 0.5, 'g' : 0.19, 'r' : 0.09, 'i' : 0.05, 'z' : 0.04}

# Fonts set by drivers.add_style later

# Default font, e.g. used for fixed labels
DEFAULT_FONT = None

# Font for menus
MENU_FONT = None

# Entry font, used for data entry points and mutable
# information
ENTRY_FONT = None

# Command log widget. Used to report actions and results
clog  = None

# Response log widget. Used to report server responses
rlog  = None

# Configuration parameter dictionary: configurable options
cpars = None

# Instrument parameters widget
ipars = None

# Run parameters widget
rpars = None

# Astronomical information widget
astro = None

# Information widget
info = None

# Focal plane slide widget
fpslide = None

# Observing widget
observe = None

# Count rates, S-to-N etc widget
count = None

# Instrument setup widget
setup = None

# Filter wheel controller
wheel = None

# Filter when 'start' last pressed
start_filter = None

# Lakeshore temperature control
lakeshore = None

# Logging file
logfile = None
