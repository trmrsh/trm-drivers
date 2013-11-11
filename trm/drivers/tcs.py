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
    
      ra     : RA, radians
      dec    : Declination, radians
      posang : position angle, radians
      focus  : focus, mm
      tflag  : True if tracking
    """

    # TNT TCS access
    url = \
        'http://192.168.20.190/TCSDataSharing/DataRequest.asmx/GetTelescopeData'
    req = urllib2.Request(url,data='',
                          headers={'content-type':'application/json'})
    response = urllib2.urlopen(req,timeout=1)
    string   = response.read()
    jsonData = json.loads(string)

    listData = eval(jsonData['d'])[0]
    #    print(listData)
    # integer, ra, dec, pa on sky [all radians], focus in m
    # string set to 'Tracking', 'Slewing' etc
    ignore,ra,dec,pa,focus,tracking = listData

    # 270 is an experimental offset which could be refined ??
    ra     = float(ra)
    dec    = float(dec)
    pa     = float(pa)+math.radians(270.)
    focus  = 1000.*float(focus)

    return (ra,dec,pa,focus,tracking == 'Tracking')
