"""
TCS access routines
"""

from __future__ import print_function
import urllib2
import json
import math

def getTntTcs():
    """
    Accesses TCS on TNT. Returns (ra,dec,posang,focus,tflag)
    where::

      ra     : RA, degrees (float)
      dec    : Declination, degrees (float)
      posang : position angle, degrees (float)
      focus  : focus, mm (float)
      tflag  : True if 'Tracking', but note that it can come back
               with True when 'Tracking' in Alt/Az mode so one needs
               to check for constant Ra, Dec as well outside this
               routine.
      engpa  : PA, degrees, related to instrument position. Not quite
               sure what it refers to but it runs from -220 to +250 deg.
               (float)
    """

    # TNT TCS access

    #   url = \
    #    'http://192.168.20.190/TCSDataSharing/DataRequest.asmx/GetTelescopeData'
    # New URL as of 28 Nov 2016 (after e-mail from Pakawat Prasit)
    url = 'http://192.168.20.190:8094/TCSDataSharing/TCSHosting'

    # get data from server
    req = urllib2.Request(url,headers={'content-type':'application/json'})
    response = urllib2.urlopen(req,timeout=2)
    string   = response.read()

    # interpret it
    jsonData = json.loads(string)
    listData = eval(jsonData)
    ignore,ra,dec,pa,focus,tracking,engpa = listData[0]

    ra     = math.degrees(float(ra))
    dec    = math.degrees(float(dec))
    pa     = math.degrees(float(pa))
    if pa < 0:
        pa += 360.
    elif pa >= 360.:
        pa -= 360.
    focus  = 1000.*float(focus)
    engpa  = math.degrees(float(engpa))

    return (ra,dec,pa,focus,tracking,engpa)
