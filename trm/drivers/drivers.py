#!/usr/bin/env python

"""
Python module supplying classes for instrument driver
GUIs. This part contains items of generic use, such as
PosInt  to multiple drivers.
"""

from __future__ import print_function
import Tkinter as tk
import tkFont
import xml.etree.ElementTree as ET
import ConfigParser
import tkFileDialog
import urllib
import urllib2
import logging
import time
import BaseHTTPServer
import SocketServer
import threading
import subprocess
import time
import math
import datetime
import json

# thirparty
import ephem

# mine
import tcs
import slide

# Zeropoints (days) of MJD, unix time and ephem,
# number of seconds in a day
MJD0  = datetime.date(1858,11,17).toordinal()
UNIX0 = datetime.date(1970,1,1).toordinal()
EPH0  = datetime.date(1899,12,31).toordinal() + 0.5
DAY   = 86400.

# may need this at some point
#proxy_support = urllib2.ProxyHandler({})
#opener = urllib2.build_opener(proxy_support)
#urllib2.install_opener(opener)

# Colours
COL = {\
    'main' : '#d0d0ff',     # Colour for the surrounds
    'text' : '#000050',     # Text colour
    'debug' : '#a0a0ff',    # Text background for debug messages
    'warn' : '#f0c050',     # Text background for warnings
    'error' : '#ffa0a0',    # Text background for errors
    'critical' : '#ff0000', # Text background for disasters
    'start' : '#aaffaa',    # Start button colour
    'stop' : '#ffaaaa',     # Stop button colour
    'log' : '#e0d4ff',      # Logger windows
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

def addStyle(root):
    """
    Styles the GUI: global fonts and colours.
    """

    # Default font
    default_font = tkFont.nametofont("TkDefaultFont")
    default_font.configure(size=8)
    root.option_add('*Font', default_font)

    # Menu font
    menu_font = tkFont.nametofont("TkMenuFont")
    menu_font.configure(size=8)
    root.option_add('*Menu.Font', menu_font)

    # Entry font
    entry_font = tkFont.nametofont("TkTextFont")
    entry_font.configure(size=8)
    root.option_add('*Entry.Font', menu_font)

    # position and size
    #    root.geometry("320x240+325+200")

    # Default colours. Note there is a difference between
    # specifying 'background' with a capital B or lowercase b
    root.option_add('*background', COL['main'])
    root.option_add('*HighlightBackground', COL['main'])
    root.config(background=COL['main'])

def loadCpars(fp):
    """
    Loads a dictionary of configuration parameters given a file object
    pointing to the configuration file. The configuration file consists
    of a series of entries of the form:

    NAME : value

    It returns a dictionary of the stored parameters, with values translated
    to appropriate types. e.g. Yes/No values become boolean, etc.
    """

    # read the configuration parameters file
    parser = ConfigParser.ConfigParser()
    parser.readfp(fp)

    # intialise dictionary
    cpars = {}

    # names / types of simple single value items needing no changes.
    SINGLE_ITEMS = {\
        'RTPLOT_SERVER_ON' : 'boolean', 'CDF_SERVERS_ON' : 'boolean',
        'EXPERT_LEVEL' : 'integer', 'FILE_LOGGING_ON' : 'boolean',
        'HTTP_CAMERA_SERVER' : 'string', 'HTTP_DATA_SERVER' : 'string',
        'APP_DIRECTORY' : 'string', 'TEMPLATE_FROM_SERVER' : 'boolean',
        'TEMPLATE_DIRECTORY' : 'string', 'LOG_FILE_DIRECTORY' : 'string',
        'CONFIRM_ON_CHANGE' : 'boolean', 'CONFIRM_HV_GAIN_ON' : 'boolean',
        'RTPLOT_SERVER_PORT' : 'integer', 'DEBUG' : 'boolean',
        'HTTP_PATH_GET' : 'string', 'HTTP_PATH_EXEC' : 'string',
        'HTTP_PATH_CONFIG' : 'string', 'HTTP_SEARCH_ATTR_NAME' : 'string',
        'INSTRUMENT_APP' : 'string', 'POWER_ON' : 'string',
        'TELINS_NAME' : 'string',
        'REQUIRE_RUN_PARAMS' : 'boolean', 'ACCESS_TCS' : 'boolean',
        'HTTP_FILE_SERVER' : 'string', 'CONFIRM_ON_QUIT' : 'boolean',
        'MDIST_WARN' : 'float'}

    for key, value in SINGLE_ITEMS.iteritems():
        if value == 'boolean':
            cpars[key.lower()] = parser.getboolean('All',key)
        elif value == 'string':
            cpars[key.lower()] = parser.get('All',key)
        elif value == 'integer':
            cpars[key.lower()] = parser.getint('All',key)
        elif value == 'float':
            cpars[key.lower()] = parser.getfloat('All',key)

    # quick check
    if cpars['expert_level'] < 0 or cpars['expert_level'] > 2:
        print('EXPERT_LEVEL must be one of 0, 1, or 2.')
        print('Please fix the configuration file = ' + fp.name)
        exit(1)

    # names with multiple values (all strings)
    MULTI_ITEMS = [\
        'FILTER_NAMES', 'FILTER_IDS', 'ACTIVE_FILTER_NAMES',
        'UAC_DATABASE_HOST']

    for item in MULTI_ITEMS:
        cpars[item.lower()] = [x.strip() for x in
                                  parser.get('All',item).split(';')]

    # Check the filters
    if not set(cpars['active_filter_names']) <= set(cpars['filter_names']):
        print('One or more of the active filter names was not recognised.')
        print('Please fix the configuration file = ' + fp.name)
        exit(1)

    # Check the telescope/instrument combo
    if cpars['telins_name'] not in TINS:
        print('Telescope/instrument combination = ' +
              cpars['telins_name'] + ' not recognised.')
        print('Current possibilities are : ' + str(TINS.keys().sort()))
        print('Please fix the configuration file = ' + fp.name)
        exit(1)

    # Special code for the templates
    labels = [x.strip() for x in parser.get('All','TEMPLATE_LABELS').split(';')]
    pairs  = [int(x.strip()) for x in
              parser.get('All','TEMPLATE_PAIRS').split(';')]
    apps   = [x.strip() for x in parser.get('All','TEMPLATE_APPS').split(';')]
    ids    = [x.strip() for x in parser.get('All','TEMPLATE_IDS').split(';')]
    if len(pairs) != len(labels) or \
            len(apps) != len(labels) or len(ids) != len(labels):
        print('TEMPLATE_LABELS, TEMPLATE_PAIRS,' +
              ' TEMPLATE_APPS and TEMPLATE_IDS must all')
        print('have the same number of items.')
        print('Please fix the configuration file = ' + fp.name)
        exit(1)

    cpars['templates'] = dict( \
        (arr[0],{'pairs' : arr[1], 'app' : arr[2], 'id' : arr[3]}) \
            for arr in zip(labels,pairs,apps,ids))
    print(cpars['templates'])
    # Next line is so that we know the order defined in the file
    cpars['template_labels'] = labels

    return cpars

class Boolean(tk.IntVar):
    """
    Defines an object representing one of the boolean
    configuration parameters to allow it to be interfaced with
    the menubar easily.
    """
    def __init__(self, flag, cpars):
        tk.IntVar.__init__(self)
        self.set(cpars[flag])
        self.trace('w', self._update)
        self.flag = flag
        self.cpars = cpars

    def _update(self, *args):
        if self.get():
            self.cpars[self.flag] = True
        else:
            self.cpars[self.flag] = False

class IntegerEntry(tk.Entry):
    """
    Defines an Entry field which only accepts integer input.
    This is the base class for several varieties of integer
    input fields.
    """

    def __init__(self, master, ival, checker, blank, **kw):
        """
        master  -- enclosing widget
        ival    -- initial integer value
        checker -- command that is run on any change to the entry
        blank   -- controls whether the field is allowed to be
                   blank. In some cases it makes things easier if
                   a blank field is allowed, even if it is technically
                   invalid (the latter case requires some other checking)
        kw      -- optional keyword arguments that can be used for
                   an Entry.
        """
        # important to set the value of _variable before tracing it
        # to avoid immediate run of _callback.
        tk.Entry.__init__(self, master, **kw)
        self._variable = tk.StringVar()
        self._value    = str(int(ival))
        self._variable.set(self._value)
        self._variable.trace("w", self._callback)
        self.config(textvariable=self._variable)
        self.checker = checker
        self.blank   = blank
        self.set_bind()

    def validate(self, value):
        """
        Applies the validation criteria.
        Returns value, new value, or None if invalid.

        Overload this in derived classes.
        """
        try:
            # trap blank fields here
            if not self.blank or value:
                int(value)
            return value
        except ValueError:
            return None

    def value(self):
        """
        Returns integer value, if possible, None if not.
        """
        try:
            return int(self._value)
        except:
            return None

    def set(self, num):
        """
        Sets the current value equal to num
        """
        print('set1: ',num,self._value)
        self._value = str(int(num))
        self._variable.set(self._value)
        print('set2: ',num,self._value)

    def add(self, num):
        """
        Adds num to the current value
        """
        try:
            val = self.value() + num
        except:
            val = num
        self.set(val)

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        try:
            val = self.value() - num
        except:
            val = -num
        self.set(val)

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        try:
            int(self._value)
            return True
        except:
            return False

    def enable(self):
        self.configure(state='normal')
        self.set_bind()

    def disable(self):
        self.configure(state='disable')
        self.set_unbind()

    def set_bind(self):
        """
        Sets key bindings.
        """
        self.bind('<Button-1>', lambda e : self.add(1))
        self.bind('<Button-3>', lambda e : self.sub(1))
        self.bind('<Up>', lambda e : self.add(1))
        self.bind('<Down>', lambda e : self.sub(1))
        self.bind('<Shift-Up>', lambda e : self.add(10))
        self.bind('<Shift-Down>', lambda e : self.sub(10))
        self.bind('<Control-Up>', lambda e : self.add(100))
        self.bind('<Control-Down>', lambda e : self.sub(100))
        self.bind('<Double-Button-1>', self._dadd)
        self.bind('<Double-Button-3>', self._dsub)
        self.bind('<Shift-Button-1>', lambda e : self.add(10))
        self.bind('<Shift-Button-3>', lambda e : self.sub(10))
        self.bind('<Control-Button-1>', lambda e : self.add(100))
        self.bind('<Control-Button-3>', lambda e : self.sub(100))
        self.bind('<Enter>', self._enter)

    def set_unbind(self):
        """
        Unsets key bindings.
        """
        self.unbind('<Button-1>')
        self.unbind('<Button-3>')
        self.unbind('<Up>')
        self.unbind('<Down>')
        self.unbind('<Shift-Up>')
        self.unbind('<Shift-Down>')
        self.unbind('<Control-Up>')
        self.unbind('<Control-Down>')
        self.unbind('<Double-Button-1>')
        self.unbind('<Double-Button-3>')
        self.unbind('<Shift-Button-1>')
        self.unbind('<Shift-Button-3>')
        self.unbind('<Control-Button-1>')
        self.unbind('<Control-Button-3>')
        self.unbind('<Enter>')

    def _callback(self, *dummy):
        """
        This gets called on any attempt to change the value
        """
        # retrieve the value from the Entry
        value = self._variable.get()

        # run the validation. Returns None if no good
        newvalue = self.validate(value)

        if newvalue is None:
            # Invalid: restores previously stored value
            # no checker run.
            self._variable.set(self._value)

        elif newvalue != value:
            # If the value is different update appropriately
            # Store new value.
            self._value = newvalue
            self._variable.set(self.newvalue)
            if self.checker:
                self.checker(*dummy)
        else:
            # Store new value
            self._value = value
            if self.checker:
                self.checker(*dummy)

    # following are callbacks for bindings
    def _dadd(self, event):
        self.add(1)
        return 'break'

    def _dsub(self, event):
        self.sub(1)
        return 'break'

    def _enter(self, event):
        self.focus()
        self.icursor(tk.END)

class PosInt (IntegerEntry):
    """
    Provide positive or 0 integer input. Basically
    an IntegerEntry with one or two extras.
    """

    def set_bind(self):
        """
        Sets key bindings -- we need this more than once
        """
        IntegerEntry.set_bind(self)
        self.bind('<Next>', lambda e : self.set(0))

    def set_unbind(self):
        """
        Unsets key bindings -- we need this more than once
        """
        IntegerEntry.set_unbind(self)
        self.unbind('<Next>')

    def validate(self, value):
        """
        Applies the validation criteria.
        Returns value, new value, or None if invalid.

        Overload this in derived classes.
        """
        try:
            # trap blank fields here
            if not self.blank or value:
                v = int(value)
                if v < 0:
                    return None
            return value
        except ValueError:
            return None

    def add(self, num):
        """
        Adds num to the current value
        """
        try:
            val = self.value() + num
        except:
            val = num
        self.set(max(0,val))

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        try:
            val = self.value() - num
        except:
            val = -num
        self.set(max(0,val))

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        try:
            v = int(self._value)
            if v < 0:
                return False
            else:
                return True
        except:
            return False

class RangedInt (IntegerEntry):
    """
    Provides range-checked integer input.
    """
    def __init__(self, master, ival, imin, imax, checker, blank, **kw):
        """
        master  -- enclosing widget
        ival    -- initial integer value
        imin    -- minimum value
        imax    -- maximum value
        checker -- command that is run on any change to the entry
        blank   -- controls whether the field is allowed to be
                   blank. In some cases it makes things easier if
                   a blank field is allowed, even if it is technically
                   invalid.
        kw      -- keyword arguments
        """
        self.imin = imin
        self.imax = imax
        IntegerEntry.__init__(self, master, ival, checker, blank, **kw)
        self.bind('<Next>', lambda e : self.set(self.imin))
        self.bind('<Prior>', lambda e : self.set(self.imax))

    def set_bind(self):
        """
        Sets key bindings -- we need this more than once
        """
        IntegerEntry.set_bind(self)
        self.bind('<Next>', lambda e : self.set(self.imin))
        self.bind('<Prior>', lambda e : self.set(self.imax))

    def set_unbind(self):
        """
        Unsets key bindings -- we need this more than once
        """
        IntegerEntry.set_unbind(self)
        self.unbind('<Next>')
        self.unbind('<Prior>')

    def validate(self, value):
        """
        Applies the validation criteria.
        Returns value, new value, or None if invalid.

        Overload this in derived classes.
        """
        try:
            # trap blank fields here
            if not self.blank or value:
                v = int(value)
                if v < self.imin or v > self.imax:
                    return None
            return value
        except ValueError:
            return None

    def add(self, num):
        """
        Adds num to the current value
        """
        try:
            print('1: ',self.value(),num)
            val = self.value() + num
            print('2: ',val,self.value(),num,self.imin,self.imax)
        except:
            val = num
        self.set(min(self.imax,max(self.imin,val)))

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        try:
            val = self.value() - num
        except:
            val = -num
        self.set(min(self.imax,max(self.imin,val)))

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        try:
            v = int(self._value)
            if v < self.imin or v > self.imax:
                return False
            else:
                return True
        except:
            return False

class RangedMint (RangedInt):
    """
    This is the same as RangedInt but locks to multiples
    """

    def __init__(self, master, ival, imin, imax, mfac, checker, blank, **kw):
        """
        mfac must be class that support 'value()' to return an integer value.
        to allow it to be updated
        """
        self.mfac = mfac
        RangedInt.__init__(self, master, ival, imin, imax, checker, blank, **kw)
        self.unbind('<Next>')
        self.unbind('<Prior>')
        self.bind('<Next>', lambda e: self.set(self._min()))
        self.bind('<Prior>', lambda e: self.set(self._max()))
        print(ival,imin,imax,mfac.value())

    def set_bind(self):
        """
        Sets key bindings -- we need this more than once
        """
        RangedInt.set_bind(self)
        self.unbind('<Next>')
        self.unbind('<Prior>')
        self.bind('<Next>', lambda e: self.set(self._min()))
        self.bind('<Prior>', lambda e: self.set(self._max()))

    def set_unbind(self):
        """
        Sets key bindings -- we need this more than once
        """
        RangedInt.set_unbind(self)
        self.unbind('<Next>')
        self.unbind('<Prior>')

    def add(self, num):
        """
        Adds num to the current value, jumping up the next
        multiple of mfac if the result is not a multiple already
        """
        try:
            val = self.value() + num
        except:
            val = num

        chunk = self.mfac.value()
        if val % chunk > 0:
            if num > 0:
                val = chunk*(val // chunk + 1)
            elif num < 0:
                val = chunk*(val // chunk)

        val = max(self._min(), min(self._max(), val))
        self.set(val)

    def sub(self, num):
        """
        Subtracts num from the current value, forcing the result to be within
        range and a multiple of mfac
        """
        try:
            val = self.value() - num
        except:
            val = -num

        chunk = self.mfac.value()
        if val % chunk > 0:
            if num > 0:
                val = chunk*(val // chunk)
            elif num < 0:
                val = chunk*(val // chunk + 1)

        val = max(self._min(), min(self._max(), val))
        self.set(val)

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        try:
            v = int(self._value)
            chunk = self.mfac.value()
            if v < self.imin or v > self.imax or (v % chunk != 0):
                return False
            else:
                return True
        except:
            return False

    def _min(self):
        chunk = self.mfac.value()
        mval  = chunk*(self.imin // chunk)
        print(chunk,mval,self.imin,mval+chunk if mval < self.imin else mval)
        return mval+chunk if mval < self.imin else mval

    def _max(self):
        chunk = self.mfac.value()
        return chunk*(self.imax // chunk)

class ListInt (IntegerEntry):
    """
    Provides integer input allowing only a finite list of integers.
    Needed for the binning factors.
    """
    def __init__(self, master, ival, allowed, checker, **kw):
        """
        master  -- enclosing widget
        ival    -- initial integer value
        allowed -- list of allowed values. Will be checked for uniqueness
        checker -- command that is run on any change to the entry
        kw      -- keyword arguments
        """
        if ival not in allowed:
            raise DriverError('drivers.ListInt: value = ' + str(ival) +
                              ' not in list of allowed values.')
        if len(set(allowed)) != len(allowed):
            raise DriverError('drivers.ListInt: not all values unique'+
                              ' in allowed list.')

        # we need to maintain an index of which integer has been selected
        self.allowed = allowed
        self.index   = allowed.index(ival)
        IntegerEntry.__init__(self, master, ival, checker, False, **kw)
        self.set_bind()


    def set_bind(self):
        """
        Sets key bindings -- we need this more than once
        """
        self.unbind('<Shift-Up>')
        self.unbind('<Shift-Down>')
        self.unbind('<Control-Up>')
        self.unbind('<Control-Down>')
        self.unbind('<Double-Button-1>')
        self.unbind('<Double-Button-3>')
        self.unbind('<Shift-Button-1>')
        self.unbind('<Shift-Button-3>')
        self.unbind('<Control-Button-1>')
        self.unbind('<Control-Button-3>')

        self.bind('<Button-1>', lambda e : self.add(1))
        self.bind('<Button-3>', lambda e : self.sub(1))
        self.bind('<Up>', lambda e : self.add(1))
        self.bind('<Down>', lambda e : self.sub(1))
        self.bind('<Enter>', self._enter)
        self.bind('<Next>', lambda e : self.set(self.allowed[0]))
        self.bind('<Prior>', lambda e : self.set(self.allowed[-1]))

    def set_unbind(self):
        """
        Unsets key bindings -- we need this more than once
        """
        self.unbind('<Button-1>')
        self.unbind('<Button-3>')
        self.unbind('<Up>')
        self.unbind('<Down>')
        self.unbind('<Enter>')
        self.unbind('<Next>')
        self.unbind('<Prior>')

    def validate(self, value):
        """
        Applies the validation criteria.
        Returns value, new value, or None if invalid.

        Overload this in derived classes.
        """
        try:
            v = int(value)
            if v not in self.allowed:
                return None
            return value
        except ValueError:
            return None

    def add(self, num):
        """
        Adds num to the current value
        """
        self.index = max(0,min(len(self.allowed)-1,self.index+num))
        self.set(self.allowed[self.index])

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        self.index = max(0,min(len(self.allowed)-1,self.index-num))
        self.set(self.allowed[self.index])

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        return True

class FloatEntry(tk.Entry):
    """
    Defines an Entry field which only accepts floating point input.
    """

    def __init__(self, master, fval, checker, blank, **kw):
        """
        master  -- enclosing widget
        ival    -- initial integer value
        checker -- command that is run on any change to the entry
        blank   -- controls whether the field is allowed to be
                   blank. In some cases it makes things easier if
                   a blank field is allowed, even if it is technically
                   invalid (the latter case requires some other checking)
        kw      -- optional keyword arguments that can be used for
                   an Entry.
        """
        # important to set the value of _variable before tracing it
        # to avoid immediate run of _callback.
        tk.Entry.__init__(self, master, **kw)
        self._variable = tk.StringVar()
        self._value = str(float(fval))
        self._variable.set(self._value)
        self._variable.trace("w", self._callback)
        self.config(textvariable=self._variable)
        self.checker = checker
        self.blank   = blank
        self.set_bind()

    def validate(self, value):
        """
        Applies the validation criteria.
        Returns value, new value, or None if invalid.

        Overload this in derived classes.
        """
        try:
            # trap blank fields here
            if not self.blank or value:
                float(value)
            return value
        except ValueError:
            return None

    def value(self):
        """
        Returns float value, if possible, None if not.
        """
        try:
            return float(self._value)
        except:
            return None

    def set(self, num):
        """
        Sets the current value equal to num
        """
        self._value = str(float(num))
        self._variable.set(self._value)

    def add(self, num):
        """
        Adds num to the current value
        """
        try:
            val = self.value() + num
        except:
            val = num
        self.set(val)

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        try:
            val = self.value() - num
        except:
            val = -num
        self.set(val)

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        try:
            float(self._value)
            return True
        except:
            return False

    def enable(self):
        self.configure(state='normal')
        self.set_bind()

    def disable(self):
        self.configure(state='disable')
        self.set_unbind()

    def set_bind(self):
        """
        Sets key bindings.
        """
        self.bind('<Button-1>', lambda e : self.add(0.1))
        self.bind('<Button-3>', lambda e : self.sub(0.1))
        self.bind('<Up>', lambda e : self.add(0.1))
        self.bind('<Down>', lambda e : self.sub(0.1))
        self.bind('<Shift-Up>', lambda e : self.add(1))
        self.bind('<Shift-Down>', lambda e : self.sub(1))
        self.bind('<Control-Up>', lambda e : self.add(10))
        self.bind('<Control-Down>', lambda e : self.sub(10))
        self.bind('<Double-Button-1>', self._dadd)
        self.bind('<Double-Button-3>', self._dsub)
        self.bind('<Shift-Button-1>', lambda e : self.add(1))
        self.bind('<Shift-Button-3>', lambda e : self.sub(1))
        self.bind('<Control-Button-1>', lambda e : self.add(10))
        self.bind('<Control-Button-3>', lambda e : self.sub(10))
        self.bind('<Enter>', self._enter)

    def set_unbind(self):
        """
        Unsets key bindings.
        """
        self.unbind('<Button-1>')
        self.unbind('<Button-3>')
        self.unbind('<Up>')
        self.unbind('<Down>')
        self.unbind('<Shift-Up>')
        self.unbind('<Shift-Down>')
        self.unbind('<Control-Up>')
        self.unbind('<Control-Down>')
        self.unbind('<Double-Button-1>')
        self.unbind('<Double-Button-3>')
        self.unbind('<Shift-Button-1>')
        self.unbind('<Shift-Button-3>')
        self.unbind('<Control-Button-1>')
        self.unbind('<Control-Button-3>')
        self.unbind('<Enter>')

    def _callback(self, *dummy):
        """
        This gets called on any attempt to change the value
        """
        # retrieve the value from the Entry
        value = self._variable.get()

        # run the validation. Returns None if no good
        newvalue = self.validate(value)

        if newvalue is None:
            # Invalid: restores previously stored value
            # no checker run.
            self._variable.set(self._value)

        elif newvalue != value:
            # If the value is different update appropriately
            # Store new value.
            self._value = newvalue
            self._variable.set(self.newvalue)
            if self.checker:
                self.checker(*dummy)
        else:
            # Store new value
            self._value = value
            if self.checker:
                self.checker(*dummy)

    # following are callbacks for bindings
    def _dadd(self, event):
        self.add(0.1)
        return 'break'

    def _dsub(self, event):
        self.sub(0.1)
        return 'break'

    def _enter(self, event):
        self.focus()
        self.icursor(tk.END)

class RangedFloat (FloatEntry):
    """
    Provides range-checked float input.
    """
    def __init__(self, master, fval, fmin, fmax, checker,
                 blank, allowzero=False, **kw):
        """
        master    -- enclosing widget
        fval      -- initial float value
        fmin      -- minimum value
        fmax      -- maximum value
        checker   -- command that is run on any change to the entry
        blank     -- controls whether the field is allowed to be
                   blank. In some cases it makes things easier if
                   a blank field is allowed, even if it is technically
                   invalid.
        allowzero -- if 0 < fmin < 1 input of numbers in the range fmin to 1
                     can be difficult unless 0 is allowed even though it is
                     an invalid value.
        kw        -- keyword arguments
        """
        self.fmin = fmin
        self.fmax = fmax
        FloatEntry.__init__(self, master, fval, checker, blank, **kw)
        self.bind('<Next>', lambda e : self.set(self.fmin))
        self.bind('<Prior>', lambda e : self.set(self.fmax))
        self.allowzero = allowzero

    def set_bind(self):
        """
        Sets key bindings -- we need this more than once
        """
        FloatEntry.set_bind(self)
        self.bind('<Next>', lambda e : self.set(self.fmin))
        self.bind('<Prior>', lambda e : self.set(self.fmax))

    def set_unbind(self):
        """
        Unsets key bindings -- we need this more than once
        """
        FloatEntry.set_unbind(self)
        self.unbind('<Next>')
        self.unbind('<Prior>')

    def validate(self, value):
        """
        Applies the validation criteria.
        Returns value, new value, or None if invalid.

        Overload this in derived classes.
        """
        try:
            # trap blank fields here
            if not self.blank or value:
                v = float(value)
                if (self.allowzero and v != 0 and v < self.fmin) or \
                        (not self.allowzero and v < self.fmin) or v > self.fmax:
                    return None
            return value
        except ValueError:
            return None

    def add(self, num):
        """
        Adds num to the current value
        """
        try:
            val = self.value() + num
        except:
            val = num
        self.set(min(self.fmax,max(self.fmin,val)))

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        try:
            val = self.value() - num
        except:
            val = -num
        self.set(min(self.fmax,max(self.fmin,val)))

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        try:
            v = float(self._value)
            if v < self.fmin or v > self.fmax:
                return False
            else:
                return True
        except:
            return False


class Expose (RangedFloat):
    """
    Special entry field for exposure times designed to return
    an integer number of 0.1ms increments.
    """
    def __init__(self, master, fval, fmin, fmax, checker, **kw):
        """
        master  -- enclosing widget
        fval    -- initial value, seconds
        fmin    -- minimum value, seconds
        fmax    -- maximum value, seconds
        checker -- command that is run on any change to the entry

        fval, fmin and fmax must be multiples of 0.0001
        """
        if round(10000*fval) != 10000*fval:
            raise DriverError(
                'drivers.Expose.__init__: fval must be a multiple of 0.0001')
        if round(10000*fmin) != 10000*fmin:
            raise DriverError(
                'drivers.Expose.__init__: fmin must be a multiple of 0.0001')
        if round(10000*fmax) != 10000*fmax:
            raise DriverError(
                'drivers.Expose.__init__: fmax must be a multiple of 0.0001')

        RangedFloat.__init__(self, master, fval, fmin,
                             fmax, checker, True, **kw)

    def validate(self, value):
        """
        This prevents setting any value more precise than 0.0001
        """
        try:
            # trap blank fields here
            if value:
                v = float(value)
                if (v != 0 and v < self.fmin) or v > self.fmax:
                    return None
                if round(10000*v) != 10000*v:
                    return None
            return value
        except ValueError:
            return None

    def ivalue(self):
        """
        Returns integer value in units of 0.1ms, if possible, None if not.
        """
        try:
            return int(round(10000*float(self._value)))
        except:
            return None

    def set_min(self, fmin):
        """
        Updates minimum value
        """
        if round(10000*fmin) != 10000*fmin:
            raise DriverError('drivers.Expose.set_min: ' + \
                                  'fmin must be a multiple of 0.0001')
        self.fmin = fmin
        self.set(self.fmin)

class TextEntry (tk.Entry):
    """
    Sub-class of Entry for basic text input. Not a lot to
    it but it keeps things neater and it has a check for
    blank entries.
    """

    def __init__(self, master, width, callback=None):
        """
        master  : the widget this gets placed inside
        """

        # Define a StringVar, connect it to the callback, if there is one
        self.val = tk.StringVar()
        if callback is not None:
            self.val.trace('w', callback)
        tk.Entry.__init__(self, master, textvariable=self.val, \
                              fg=COL['text'], bg=COL['main'], width=width)

        # Control input behaviour.
        self.bind('<Enter>', lambda e : self.focus())

    def value(self):
        """
        Returns value.
        """
        return self.val.get()

    def set(self, text):
        """
        Returns value.
        """
        return self.val.set(text)

    def ok(self):
        if self.value() == '' or self.value().isspace():
            return False
        else:
            return True

class Choice(tk.OptionMenu):
    """
    Menu choice class.
    """
    def __init__(self, master, options, initial=None, width=0, checker=None):
        """
        master  : containing widget
        options : list of strings
        initial : the initial one to select. If None will default to the first.
        width   : minimum character width to use. Width set will be large
                  enough for longest option.
        checker : callback to run on any change of selection.
        """

        self.val = tk.StringVar()
        if initial is None:
            self.val.set(options[0])
        else:
            self.val.set(initial)
        tk.OptionMenu.__init__(self, master, self.val, *options)
        width = max(width, reduce(max, [len(s) for s in options]))
        self.config(width=width)
        self.checker = checker
        if self.checker is not None:
            self.val.trace('w', self.checker)
        self.options = options

    def value(self):
        return self.val.get()

    def set(self, choice):
        return self.val.set(choice)

    def disable(self):
        self.configure(state='disable')

    def enable(self):
        self.configure(state='normal')

    def getIndex(self):
        """
        Returns the index of the selected choice,
        Throws a ValueError if the set value is not
        one of the options.
        """
        return self.options.index(self.val.get())


class Radio(tk.Frame):
    """
    Left-to-right radio button class. Lays out buttons in a grid
    from left-to-right. Has a max number of columns after which it
    will jump to left of next row and start over.
    """
    def __init__(self, master, options, ncmax, checker=None,
                 values=None, initial=0):
        """
        master : containing widget
        options : array of option strings, in order. These are the choices
        presented to the user.
        ncmax : max number of columns (flows onto next row if need be)
        checker : callback to be run after any change
        values : array of string values used by the code internally.
        If 'None', the value from 'options' will be used.
        initial : index of initial value to set.
        """
        tk.Frame.__init__(self, master)
        if values is not None and len(values) != len(options):
            raise DriverError('drvs.Radio.__init__: values and ' + \
                                  'options must have same length')

        self.val = tk.StringVar()
        if values is None:
            self.val.set(options[initial])
        else:
            self.val.set(values[initial])

        row = 0
        col = 0
        self.buttons = []
        for nopt, option in enumerate(options):
            if values is None:
                self.buttons.append(
                    tk.Radiobutton(self, text=option, variable=self.val,
                                   value=option))
                self.buttons[-1].grid(row=row, column=col, sticky=tk.W)
            else:
                self.buttons.append(
                    tk.Radiobutton(self, text=option, variable=self.val,
                                   value=values[nopt]))
                self.buttons[-1].grid(row=row, column=col, sticky=tk.W)
            col += 1
            if col == ncmax:
                row += 1
                col = 0

        self.checker = checker
        if self.checker is not None:
            self.val.trace('w', self.checker)
        self.options = options

    def value(self):
        return self.val.get()

    def set(self, choice):
        return self.val.set(choice)

    def disable(self):
        for b in self.buttons:
            b.configure(state='disable')

    def enable(self):
        for b in self.buttons:
            b.configure(state='normal')

    def getIndex(self):
        """
        Returns the index of the selected choice,
        Throws a ValueError if the set value is not
        one of the options.
        """
        return self.options.index(self.val.get())

class OnOff(tk.Checkbutton):
    """
    On or Off choice
    """

    def __init__(self, master, value, checker=None):
        self.val = tk.IntVar()
        self.val.set(value)
        tk.Checkbutton.__init__(
            self, master, variable=self.val, command=checker)

    def __call__(self):
        return self.val.get()

    def disable(self):
        self.configure(state='disable')

    def enable(self):
        self.configure(state='normal')

    def set(self, state):
        self.val.set(state)

def overlap(xl1,yl1,nx1,ny1,xl2,yl2,nx2,ny2):
    """
    Determines whether two windows overlap
    """
    return (xl2 < xl1+nx1 and xl2+nx2 > xl1 and \
                yl2 < yl1+ny1 and yl2+ny2 > yl1)

def saveXML(root, clog):
    """
    Saves the current setup to disk.

    root : (xml.etree.ElementTree.Element)
    The current setup.
    """
    fname = tkFileDialog.asksaveasfilename(
        defaultextension='.xml', filetypes=[('xml files', '.xml'),])
    if not fname:
        clog.log.warn('Aborted save to disk\n')
        return False
    tree = ET.ElementTree(root)
    tree.write(fname)
    clog.log.info('Saved setup to' + fname + '\n')
    return True

def postXML(root, cpars, clog, rlog):
    """
    Posts the current setup to the camera and data servers.

    root : (xml.etree.ElementTree.Element)
    The current setup.

    cpars : (dict)
    Configuration parameters inc. urls of servers
    """
    clog.log.debug('Entering postXML\n')

    if not cpars['cdf_servers_on']:
        clog.log.warn('postXML: cdf_servers_on set to False\n')
        return False

    # Write setup to an xml string
    sxml = ET.tostring(root)

    # Send the xml to the camera server
    url = cpars['http_camera_server'] + cpars['http_path_config']
    clog.log.debug('Camera URL = ' + url +'\n')

    opener = urllib2.build_opener()
    clog.log.debug('content length = ' + str(len(sxml)) + '\n')
    req = urllib2.Request(url, data=sxml, headers={'Content-type': 'text/xml'})
    response = opener.open(req, timeout=5)
    csr	 = ReadServer(response.read())
    rlog.log.warn(csr.resp() + '\n')
    if not csr.ok:
        clog.log.warn('Camera response was not OK\n')
        return False

    # Send the xml to the data server
    url = cpars['http_data_server'] + cpars['http_path_config']
    clog.log.debug('Data server URL = ' + url + '\n')
    req = urllib2.Request(url, data=sxml, headers={'Content-type': 'text/xml'})
    response = opener.open(req, timeout=5) # ?? need to check whether this is needed
    fsr	 = ReadServer(response.read())
    rlog.log.warn(fsr.resp() + '\n')
    if not csr.ok:
        clog.log.warn('Fileserver response was not OK\n')
        return False

    clog.log.debug('Leaving postXML\n')
    return True

class ActButton(tk.Button):
    """
    Base class for action buttons. This keeps an internal flag
    representing whether the button should be active or not.
    Whether it actually is, might be overridden, but the internal
    flag tracks the (potential) activity status allowing it to be
    reset. The 'expert' flag controls whether the activity status
    will be overridden. The button starts out in non-expert mode by
    default. This can be switches with setExpert, setNonExpert.
    """

    def __init__(self, master, width, share, callback=None, **kwargs):
        """
        master   : containing widget
        width    : width in characters of the button
        share    : dictionary of other objects that might need to be accessed
        callback : callback function
        bg       : background colour
        kwargs   : keyword arguments
        """
        tk.Button.__init__(
            self, master, fg='black', width=width, command=self.act, **kwargs)

        # store some attributes. other anc calbback are obvious.
        # _active indicates whether the button should be enabled or disabled
        # _expert indicates whether the activity state should be overridden so
        #         that the button is enabled in any case (if set True)
        self.share    = share
        self.callback = callback
        self._active  = True
        self._expert  = False

    def enable(self):
        """
        Enable the button, set its activity flag.
        """
        self.configure(state='normal')
        self._active = True

    def disable(self):
        """
        Disable the button, if in non-expert mode,
        unset its activity flag come-what-may
        """
        if not self._expert:
            self.configure(state='disable')
        self._active = False

    def setExpert(self):
        """
        Turns on 'expert' status whereby the button is always enabled,
        regardless of its activity status.
        """
        self._expert = True
        print('1 setExpert activity flag =',self._active)
        self.configure(state='normal')
        print('2 setExpert activity flag =',self._active)

    def setNonExpert(self):
        """
        Turns off 'expert' status whereby to allow a button to be disabled
        """
        self._expert = False
        print('setNonExpert activity flag =',self._active)
        if self._active:
            self.enable()
        else:
            self.disable()

    def act(self):
        """
        Carry out the action associated with the button.
        Override in derived classes
        """
        self.callback()

class Stop(ActButton):
    """
    Class defining the 'Stop' button's operation
    """

    def __init__(self, master, width, share):
        """
        master   : containing widget
        width    : width of button
        share    : dictionary with configuration parameters and the loggers
        """

        ActButton.__init__(
            self, master, width, share, bg=COL['stop'], text='Stop')

    def act(self):
        """
        Carries out the action associated with Stop button
        """

        o = self.share
        cpars, clog, rlog = o['cpars'], o['clog'], o['rlog']

        clog.log.debug('Stop pressed\n')

        if execCommand('EX,0', cpars, clog, rlog):
            clog.log.info('Run stopped\n')

            # modify buttons
            self.disable()
            o['Start'].disable()
            o['setup'].resetSDSUhard.enable()
            o['setup'].resetSDSUsoft.enable()
            o['setup'].resetPCI.disable()
            o['setup'].setupServers.disable()
            o['setup'].powerOn.disable()
            o['setup'].powerOff.enable()

            # stop exposure meter
            o['info'].timer.stop()
            return True
        else:
            clog.log.warn('Failed to stop run\n')
            return False

class Target(tk.Frame):
    """
    Class wrapping up what is needed for a target name which
    is an entry field and a verification button. The verification
    button checks for simbad recognition and goes green or red
    according to the results. If no check has been made, it has
    a default colour.
    """
    def __init__(self, master, share, callback=None):
        tk.Frame.__init__(self, master)

        # Entry field, linked to a StringVar which is traced for
        # any modification
        self.val    = tk.StringVar()
        self.val.trace('w', self.modver)
        self.entry  = tk.Entry(
            self, textvariable=self.val, fg=COL['text'],
            bg=COL['main'], width=25)
        self.entry.bind('<Enter>', lambda e : self.entry.focus())

        # Verification button which accesses simbad to see if
        # the target is recognised.
        self.verify = tk.Button(
            self, fg='black', width=8, text='Verify',
            bg=COL['main'], command=self.act)
        self.entry.pack(side=tk.LEFT,anchor=tk.W)
        self.verify.pack(side=tk.LEFT,anchor=tk.W,padx=5)
        self.verify.config(state='disable')
        self.share  = share
        self.callback = callback

    def value(self):
        """
        Returns value.
        """
        return self.val.get()

    def set(self, text):
        """
        Sets value.
        """
        return self.val.set(text)

    def ok(self):
        if self.val.get() == '' or self.val.get().isspace():
            return False
        else:
            return True

    def modver(self, *args):
        """
        Switches colour of verify button
        """
        if self.ok():
            self.verify.config(bg=COL['main'])
            self.verify.config(state='normal')
        else:
            self.verify.config(bg=COL['main'])
            self.verify.config(state='disable')

        if self.callback is not None:
            self.callback()

    def act(self):
        """
        Carries out the action associated with Verify button
        """

        o = self.share
        clog, rlog = o['clog'], o['rlog']
        tname = self.val.get()

        clog.log.debug('Checking "' + tname + '" with simbad\n')
        ret = checkSimbad(tname)
        if len(ret) == 0:
            self.verify.config(bg=COL['error'])
            clog.log.warn('No matches to "' + tname + '" found\n')
        else:
            self.verify.config(bg=COL['main'])
            self.verify.config(state='disable')
            rlog.log.info('Target verified OK\n')
            rlog.log.info(
                'Found ' + str(len(ret)) + ' matches to "' + tname + '"\n')
            for entry in ret:
                rlog.log.info(
                    'Name: ' + entry['Name'] + ', position: ' +
                    entry['Position'] + '\n')

class ReadServer(object):
    """
    Class to field the xml responses sent back from the ULTRACAM servers

    Set the following attributes:

     root    : the xml.etree.ElementTree.Element at the root of the xml
     camera  : true if the response was from the camera server (else filesave)
     ok      : whether response is OK or not (True/False)
     err     : message if ok == False
     state   : state of the camera. Possibilties are:
               'IDLE', 'BUSY', 'ERROR', 'ABORT', 'UNKNOWN'
     run     : current or last run number
    """

    def __init__(self, resp):
        # Store the entire response
        self.root = ET.fromstring(resp)

        # Identify the source: camera or filesave
        cfind = self.root.find('source')
        if cfind is None:
            self.camera = None
            self.ok     = False
            self.err    = 'Could not identify source'
            self.state  = None
            return

        self.camera = cfind.text.find('Camera') > -1

        # strip excess stuff
        camstat = self.root.find('camera_status')
        if camstat is not None:
            self.root.remove(camstat)

        filestat = self.root.find('filesave_status')
        if filestat is not None:
            self.root.remove(filestat)

        # Work out whether it was happy
        sfind = self.root.find('status')
        if sfind is None:
            self.ok    = False
            self.err   = 'Could not identify status'
            self.state = None
            return

        att = sfind.attrib
        if 'software' in att and 'errnum' in att:
            self.ok = att['software'] == 'OK'
            if self.ok:
                self.err = ''
            else:
                self.err = 'server errnum = ' + str(att['errnum'])

        # Determine state of the camera / data server
        sfind = self.root.find('state')
        if sfind is None:
            self.ok     = False
            self.err    = 'Could not identify state'
            self.state  = None
            return

        if self.camera:
            self.state = sfind.attrib['camera']
        else:
            self.state = sfind.attrib['server']

        # Find current run number (set it to 0 if we fail)
        # this only works for  the 'fstatus' command as
        # opposed to 'status' for which the above works
        sfind = self.root.find('lastfile')
        if sfind is not None and 'path' in sfind.attrib:
            self.run = int(sfind.attrib['path'][-3:])
        else:
            self.run = 0

    def resp(self):
        return ET.tostring(self.root)

def execCommand(command, cpars, clog, rlog):
    """
    Executes a command by sending it to the camera server

    Arguments:

      command : (string)
           the command (see below)

      cpars : (dict)
           configuration parameters

      clog :
           logger of commands

      rlog :
           logger of responses

    Possible commands are:

      GO   : starts a run
      ST   : stops a run
      EX,0 : stops a run
      RCO  : resets the timing board (SDSU hardware reset)
      RS   : resets the timing board (SDSU software reset)
      RST  : resets the PCI board (software)
      SRS  :
      RM,X,0x80: to get version

    Returns True/False according to whether the command
    succeeded or not.
    """
    if not cpars['cdf_servers_on']:
        clog.log.warn('execCommand: cdf_servers_on set to False\n')
        return False

    try:
        url = cpars['http_camera_server'] + cpars['http_path_exec'] + \
            '?' + command
        clog.log.info('execCommand, command = "' + command + '"\n')
        response = urllib2.urlopen(url)
        rs  = ReadServer(response.read())

        rlog.log.info('Camera response =\n' + rs.resp() + '\n')
        if rs.ok:
            clog.log.info('Response from camera server was OK\n')
            return True
        else:
            clog.log.warn('Response from camera server was not OK\n')
            clog.log.warn('Reason: ' + rs.err + '\n')
            return False
    except urllib2.URLError, err:
        clog.log.warn('execCommand failed\n')
        clog.log.warn(str(err) + '\n')

    return False

def execServer(name, app, cpars, clog, rlog):
    """
    Sends application to a server

    Arguments:

      name : (string)
         'camera' or 'data' for the camera or data server

      app : (string)
           the appication name

      cpars : (dict)
           configuration parameters

      clog :
          command log

      rlog :
          response log

    Returns True/False according to success or otherwise
    """
    if not cpars['cdf_servers_on']:
        clog.log.warn('execServer: cdf_servers_on set to False\n')
        return False

    print(cpars['http_camera_server'], cpars['http_path_config'], '?', app)

    if name == 'camera':
        url = cpars['http_camera_server'] + cpars['http_path_config'] + \
            '?' + app
    elif name == 'data':
        url = cpars['http_data_server'] + cpars['http_path_config'] + '?' + app
    else:
        raise Exception('Server name = ' + name + ' not recognised.')

    clog.log.debug('execServer, url = ' + url + '\n')

    response = urllib2.urlopen(url)
    rs  = ReadServer(response.read())
    if not rs.ok:
        clog.log.warn('Response from ' + name + ' server not OK\n')
        clog.log.warn('Reason: ' + rs.err + '\n')
        return False

    clog.log.debug('execServer command was successful\n')
    return True

def execRemoteApp(app, cpars, clog, rlog):
    """
    Executes a remote application by sending it first to the
    camera and then to the data server.

    Arguments:

      app : (string)
           the application command (see below)

      cpars : (dict)
           configuration parameters

      clog :
          command log

      rlog :
          response log

    Returns True/False according to whether the command
    succeeded or not.
    """

    return execServer('camera', app, cpars, clog, rlog) and \
        execServer('data', app, cpars, clog, rlog)

class ResetSDSUhard(ActButton):
    """
    Class defining the 'Reset SDSU hardware' button
    """

    def __init__(self, master, width, share):
        """
        master   : containing widget
        width    : width of button
        share    : dictionary of other objects
        """

        ActButton.__init__(
            self, master, width, share, text='Reset SDSU hardware')

    def act(self):
        """
        Carries out the action associated with the Reset SDSU hardware button
        """

        o = self.share
        cpars, clog, rlog = o['cpars'], o['clog'], o['rlog']

        clog.log.debug('Reset SDSU hardware pressed\n')

        if execCommand('RCO', cpars, clog, rlog):
            clog.log.info('Reset SDSU hardware succeeded\n')

            # adjust buttons
            self.disable()
            o['observe'].start.disable()
            o['observe'].stop.disable()
            o['Reset SDSU software'].disable()
            o['Reset PCI'].enable()
            o['Setup servers'].disable()
            o['Power on'].disable()
            o['Power off'].disable()
            return True
        else:
            clog.log.warn('Reset SDSU hardware failed\n')
            return False

class ResetSDSUsoft(ActButton):
    """
    Class defining the 'Reset SDSU software' button
    """

    def __init__(self, master, width, share):
        """
        master   : containing widget
        width    : width of button
        share    : dictionary of other objects
        """

        ActButton.__init__(
            self, master, width, share, text='Reset SDSU software')

    def act(self):
        """
        Carries out the action associated with the Reset SDSU software button
        """

        o = self.share
        cpars, clog, rlog = o['cpars'], o['clog'], o['rlog']

        clog.log.debug('Reset SDSU software pressed\n')

        if execCommand('RS', cpars, clog, rlog):
            clog.log.info('Reset SDSU software succeeded\n')

            # alter buttons
            self.disable()
            o['observe'].start.disable()
            o['observe'].stop.disable()
            o['Reset SDSU hardware'].disable()
            o['Reset PCI'].enable()
            o['Setup servers'].disable()
            o['Power on'].disable()
            o['Power off'].disable()
            return True
        else:
            clog.log.warn('Reset SDSU software failed\n')
            return False

class ResetPCI(ActButton):
    """
    Class defining the 'Reset PCI' button
    """

    def __init__(self, master, width, share):
        """
        master   : containing widget
        width    : width of button
        share    : dictionary with cpars, observe, clog, rlog
        """

        ActButton.__init__(self, master, width, share, text='Reset PCI')

    def act(self):
        """
        Carries out the action associated with the Reset PCI button
        """
        o = self.share
        cpars, clog, rlog = o['cpars'], o['clog'], o['rlog']

        clog.log.debug('Reset PCI pressed\n')

        if execCommand('RST', cpars, clog, rlog):
            clog.log.info('Reset PCI succeeded\n')

            # alter buttons
            self.disable()
            o['observe'].start.disable()
            o['observe'].stop.disable()
            o['Reset SDSU hardware'].enable()
            o['Reset SDSU software'].enable()
            o['Setup servers'].enable()
            o['Power on'].disable()
            o['Power off'].disable()
            return True
        else:
            clog.log.warn('Reset PCI failed\n')
            return False

class SystemReset(ActButton):
    """
    Class defining the 'System Reset' button
    """

    def __init__(self, master, width, share):
        """
        master   : containing widget
        width    : width of button
        share    : dictionary with cpars, observe, clog, rlog
        """

        ActButton.__init__(self, master, width, share, text='System Reset')

    def act(self):
        """
        Carries out the action associated with the System Reset
        """
        o = self.share
        cpars, clog, rlog = o['cpars'], o['clog'], o['rlog']

        clog.log.debug('System Reset pressed\n')

        if execCommand('SRS', cpars, clog, rlog):
            clog.log.info('System Reset succeeded\n')

            # alter buttons here
            o['observe'].start.disable()
            o['observe'].stop.disable()
            o['Reset SDSU hardware'].disable()
            o['Reset SDSU software'].disable()
            o['Reset PCI'].enable()
            o['Setup servers'].disable()
            o['Power off'].disable()
            o['Power on'].disable()
            return True
        else:
            clog.log.warn('System Reset failed\n')
            return False

class SetupServers(ActButton):
    """
    Class defining the 'Setup servers' button
    """

    def __init__(self, master, width, share):
        """
        master   : containing widget
        width    : width of button
        share    : dictionary with cpars, observe, clog, rlog
        """

        ActButton.__init__(self, master, width, share, text='Setup servers')

    def act(self):
        """
        Carries out the action associated with the 'Setup servers' button
        """
        o = self.share
        cpars, clog, rlog = o['cpars'], o['clog'], o['rlog']

        clog.log.debug('Setup servers pressed\n')
        tapp = TINS[cpars['telins_name']]['app']

        if execServer('camera', tapp, cpars, clog, rlog) and \
                execServer(
            'camera', cpars['instrument_app'], cpars, clog, rlog) and \
            execServer('data', tapp, cpars, clog, rlog) and \
            execServer('data', cpars['instrument_app'], cpars, clog, rlog):

            clog.log.info('Setup servers succeeded\n')

            # alter buttons
            self.disable()
            o['observe'].start.disable()
            o['observe'].stop.disable()
            o['Reset SDSU hardware'].enable()
            o['Reset SDSU software'].enable()
            o['Reset PCI'].disable()
            o['Power on'].enable()
            o['Power off'].disable()

            return True
        else:
            clog.log.warn('Setup servers failed\n')
            return False

class PowerOn(ActButton):
    """
    Class defining the 'Power on' button's operation
    """

    def __init__(self, master, width, share):
        """
        master  : containing widget
        width   : width of button
        share   : other objects
        """

        ActButton.__init__(self, master, width, share, text='Power on')

    def act(self):
        """
        Power on action
        """
        # shortening
        o = self.share
        cpars, clog, rlog = o['cpars'], o['clog'], o['rlog']

        clog.log.debug('Power on pressed\n')

        if execRemoteApp(cpars['power_on'], cpars, clog, rlog) and \
                execCommand('GO', cpars, clog, rlog):

            clog.log.info('Power on successful\n')

            # change other buttons
            o['observe'].start.enable()
            o['observe'].stop.disable()
            o['Reset SDSU hardware'].enable()
            o['Reset SDSU software'].enable()
            o['Reset PCI'].disable()
            o['Setup servers'].disable()
            o['Power off'].enable()
            self.disable()

            try:
                # now check the run number -- lifted from Java code; the wait
                # for the power on application to finish may not be needed
                n = 0
                while isRunActive(cpars) and n < 5:
                    n += 1
                    time.sleep(1)

                if isRunActive(cpars):
                    clog.log.warn(
                        'Timed out waiting for power on run to ' + \
                            'de-activate; cannot initialise run number. ' + \
                            'Tell trm if this happens')
                else:
                    o['info'].run.configure(text='{0:03d}'.format(getRunNumber(cpars,rlog,True)))
            except Exception, err:
                clog.log.warn(\
                    'Failed to determine run number at start of run\n')
                clog.log.warn(str(err) + '\n')
                o['info'].run.configure(text='UNDEF')
            return True
        else:
            clog.log.warn('Power on failed\n')
            return False

class PowerOff(ActButton):
    """
    Class defining the 'Power off' button's operation
    """

    def __init__(self, master, width, share):
        """
        master  : containing widget
        width   : width of button
        share   : other objects
        """

        ActButton.__init__(self, master, width, share, text='Power off')
        self.disable()

    def act(self):
        """
        Power off action
        """
        # shortening
        o = self.share
        cpars, clog, rlog = o['cpars'], o['clog'], o['rlog']

        clog.log.debug('Power off pressed\n')
        clog.log.debug('This is a placeholder as there is no Power' + \
                           ' off application so it will fail\n')

        if execRemoteApp(cpars['power_off'], cpars, clog, rlog) and \
                execCommand('GO', cpars, clog, rlog):

            clog.log.info('Powered off SDSU\n')
            self.disable()

            # alter other buttons
            o['observe'].start.disable()
            o['observe'].stop.disable()
            o['Reset SDSU hardware'].enable()
            o['Reset SDSU software'].enable()
            o['Reset PCI'].disable()
            o['Setup servers'].disable()
            o['Power on'].enable()

            return True
        else:
            clog.log.warn('Power off failed\n')
            return False

class Initialise(ActButton):
    """
    Class defining the 'Initialise' button's operation
    """

    def __init__(self, master, width, share):
        """
        master  : containing widget
        width   : width of button
        share   : other objects
        """

        ActButton.__init__(self, master, width, share, text='Initialise')

    def act(self):
        """
        Initialise action
        """
        # shortening
        o = self.share
        cpars, clog, rlog = o['cpars'], o['clog'], o['rlog']

        clog.log.debug('Initialise pressed\n')

        if not o['System reset'].act():
            clog.log.warn('Initialise failed on system reset\n')
            return False

        if not o['Setup servers'].act():
            clog.log.warn('Initialise failed on server setup\n')
            return False

        if not o['Power on'].act():
            clog.log.warn('Initialise failed on power on\n')
            return False

        clog.log.info('Initialise succeeded\n')
        return True

class InstSetup(tk.LabelFrame):
    """
    Instrument configuration frame.
    """

    def __init__(self, master, share):
        """
        master -- containing widget
        share  -- dictionary of other objects that this needs to access
        """
        tk.LabelFrame.__init__(
            self, master, text='Instrument setup', padx=10, pady=10)

        # Define all buttons
        width = 15
        self.resetSDSUhard = ResetSDSUhard(self, width, share)
        self.resetSDSUsoft = ResetSDSUsoft(self, width, share)
        self.resetPCI      = ResetPCI(self, width, share)
        self.systemReset   = SystemReset(self, width, share)
        self.setupServers  = SetupServers(self, width, share)
        self.powerOn       = PowerOn(self, width, share)
        self.initialise    = Initialise(self, width, share)
        width = 8
        self.powerOff      = PowerOff(self, width, share)

        # share all the buttons
        share['Reset SDSU hardware'] = self.resetSDSUhard
        share['Reset SDSU software'] = self.resetSDSUsoft
        share['Reset PCI']           = self.resetPCI
        share['System reset']        = self.systemReset
        share['Setup servers']       = self.setupServers
        share['Initialise']          = self.initialise
        share['Power on']            = self.powerOn
        share['Power off']           = self.powerOff

        # save
        self.share = share

        # set which buttons are presented and where they go
        self.setExpertLevel(share['cpars']['expert_level'])

    def setExpertLevel(self, level):
        """
        Set expert level
        """

        # first define which buttons are visible
        if level == 0:
            # simple layout
            self.resetSDSUhard.grid_forget()
            self.resetSDSUsoft.grid_forget()
            self.resetPCI.grid_forget()
            self.systemReset.grid_forget()
            self.setupServers.grid_forget()
            self.powerOn.grid_forget()
            self.powerOff.grid_forget()
            self.initialise.grid_forget()

            # then re-grid the two simple ones
            self.initialise.grid(row=0,column=0)
            self.powerOff.grid(row=0,column=1)

        elif level == 1 or level == 2:
            # first remove all possible buttons
            self.resetSDSUhard.grid_forget()
            self.resetSDSUsoft.grid_forget()
            self.resetPCI.grid_forget()
            self.systemReset.grid_forget()
            self.setupServers.grid_forget()
            self.powerOn.grid_forget()
            self.powerOff.grid_forget()
            self.initialise.grid_forget()

            # restore detailed layout
            row    = 0
            column = 0
            self.resetSDSUhard.grid(row=row,column=column)
            row += 1
            self.resetSDSUsoft.grid(row=row,column=column)
            row += 1
            self.resetPCI.grid(row=row,column=column)
            row += 1
            self.systemReset.grid(row=row,column=column)
            row += 1
            self.setupServers.grid(row=row,column=column)
            row += 1
            self.powerOn.grid(row=row,column=column)

            # next column
            row = 0
            column += 1
            self.powerOff.grid(row=row,column=column)

        # now set whether buttons are permanently enabled or not
        if level == 0 or level == 1:
            self.resetSDSUhard.setNonExpert()
            self.resetSDSUsoft.setNonExpert()
            self.resetPCI.setNonExpert()
            self.systemReset.setNonExpert()
            self.setupServers.setNonExpert()
            self.powerOn.setNonExpert()
            self.powerOff.setNonExpert()
            self.initialise.setNonExpert()

        elif level == 2:
            self.resetSDSUhard.setExpert()
            self.resetSDSUsoft.setExpert()
            self.resetPCI.setExpert()
            self.systemReset.setExpert()
            self.setupServers.setExpert()
            self.powerOn.setExpert()
            self.powerOff.setExpert()
            self.initialise.setExpert()

class LoggingToGUI(logging.Handler):
    """
    Used to redirect logging output to the widget passed in parameters
    """
    def __init__(self, console):
        """
        console : widget to display logging messages
        """
        logging.Handler.__init__(self)
        self.console = console
        self.console.tag_config('debug', background=COL['debug'])
        self.console.tag_config('warn', background=COL['warn'])
        self.console.tag_config('error', background=COL['error'])
        self.console.tag_config('critical', background=COL['critical'])
        self.console.tag_config('debug', background=COL['debug'])

    def emit(self, message):
        """
        Overwrites the default handler's emit method:

        message : the message to display
        """
        formattedMessage = self.format(message)

        # Write message to console
        self.console.configure(state=tk.NORMAL)
        if message.levelname == 'DEBUG':
            self.console.insert(tk.END, formattedMessage, ('debug'))
        elif message.levelname == 'INFO':
            self.console.insert(tk.END, formattedMessage)
        elif message.levelname == 'WARNING':
            self.console.insert(tk.END, formattedMessage, ('warn'))
        elif message.levelname == 'ERROR':
            self.console.insert(tk.END, formattedMessage, ('error'))
        elif message.levelname == 'CRITICAL':
            self.console.insert(tk.END, formattedMessage, ('critical'))
        else:
            print('Do not recognise level = ' + message.levelname)

        # Prevent further input
        self.console.configure(state=tk.DISABLED)
        self.console.see(tk.END)

class LogDisplay(tk.LabelFrame):
    """
    A simple logging console
    """

    def __init__(self, root, height, width, text, **options):

        tk.LabelFrame.__init__(self, root, text=text, **options);

        scrollbar = tk.Scrollbar(self)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.console = tk.Text(
            self, height=height, width=width, bg=COL['log'],
            yscrollcommand=scrollbar.set)
        self.console.configure(state=tk.DISABLED)
        self.console.pack(side=tk.LEFT)
        scrollbar.config(command=self.console.yview)

        # make a handler for GUIs
        ltgh = LoggingToGUI(self.console)

        # define the formatting
        logging.Formatter.converter = time.gmtime
        formatter = logging.Formatter('%(asctime)s - %(message)s','%H:%M:%S')
        ltgh.setFormatter(formatter)

        # make a logger and set the handler
        self.log = logging.getLogger(text)
        self.log.addHandler(ltgh)


class Switch(tk.Frame):
    """
    Frame sub-class to switch between setup, focal plane slide
    and observing frames. Provides radio buttons and hides / shows
    respective frames
    """
    def __init__(self, master, share):
        """
        master : containing widget
        share  : pass the widgets to select between
        """
        tk.Frame.__init__(self, master)

        self.val = tk.StringVar()
        self.val.set('Setup')
        self.val.trace('w', self._changed)

        tk.Radiobutton(self, text='Setup', variable=self.val,
                       value='Setup').grid(row=0, column=0, sticky=tk.W)
        tk.Radiobutton(self, text='Focal plane slide', variable=self.val,
                       value='Focal plane slide').grid(
            row=0, column=1, sticky=tk.W)
        tk.Radiobutton(self, text='Observe', variable=self.val,
                       value='Observe').grid(row=0, column=2, sticky=tk.W)

        self.observe = share['observe']
        self.fpslide = share['fpslide']
        self.setup   = share['setup']

    def _changed(self, *args):
        if self.val.get() == 'Setup':
            self.setup.pack(anchor=tk.W, pady=10)
            self.fpslide.pack_forget()
            self.observe.pack_forget()

        elif self.val.get() == 'Focal plane slide':
            self.setup.pack_forget()
            self.fpslide.pack(anchor=tk.W, pady=10)
            self.observe.pack_forget()

        elif self.val.get() == 'Observe':
            self.setup.pack_forget()
            self.fpslide.pack_forget()
            self.observe.pack(anchor=tk.W, pady=10)

        else:
            raise DriverError('Unrecognised Switch value')

class ExpertMenu(tk.Menu):
    """
    Provides a menu to select the level of expertise wanted
    when interacting with a control GUI. This setting might
    be used to hide buttons for instance according to
    the status of others, etc.
    """
    def __init__(self, master, cpars, *args):
        """
        master   -- the containing widget, e.g. toolbar menu
        cpars -- configuration parameters containing expert_level which is
                    is used to store initial value and to pass changed value
        args     -- other objects that have a 'setExpertLevel(elevel)' method.
        """
        tk.Menu.__init__(self, master, tearoff=0)

        self.val = tk.IntVar()
        self.val.set(cpars['expert_level'])
        self.val.trace('w', self._change)
        self.add_radiobutton(label='Level 0', value=0, variable=self.val)
        self.add_radiobutton(label='Level 1', value=1, variable=self.val)
        self.add_radiobutton(label='Level 2', value=2, variable=self.val)

        self.cpars = cpars
        self.args  = args

    def _change(self, *args):
        elevel = self.val.get()
        self.cpars['expert_level'] = elevel
        for arg in self.args:
            arg.setExpertLevel(elevel)


class RtplotHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """
    Handler for requests from rtplot. It accesses the window
    parameters via the 'server' attribute; the Server class
    that comes next stores these in on instantiation.
    """
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        wins = self.server.instpars.getRtplotWins()
        if wins == '':
            self.wfile.write('No valid data available\r\n')
        else:
            self.wfile.write(wins)

class RtplotServer (SocketServer.TCPServer):
    """
    Server for requests from rtplot.
    The response delivers the binning factors, number of windows and
    their positions.
    """
    def __init__(self, instpars, port):
        SocketServer.TCPServer.__init__(self, ('localhost', port),
                                        RtplotHandler)
        self.instpars = instpars

    def run(self):
        while True:
            try:
                self.serve_forever()
            except Exception, e:
                print('RtplotServer.run', e)

class Timer(tk.Label):
    """
    Run Timer class. Updates @10Hz, checks
    run status @1Hz. Switches button statuses
    when the run stops.
    """
    def __init__(self, master, share):
        tk.Label.__init__(self, master, text='{0:<d} s'.format(0))
        self.id    = None
        self.share = share
        self.count = 0

    def start(self):
        """
        Starts the timer from zero
        """
        self.startTime = time.time()
        self.configure(text='{0:<d} s'.format(0))
        self.update()

    def update(self):
        """
        Updates @ 10Hz to give smooth running clock, checks
        run status @1Hz to reduce load on servers.
        """
        delta = int(round(time.time()-self.startTime))
        self.configure(text='{0:<d} s'.format(delta))

        self.count += 1
        if self.count % 10 == 0:
            o = self.share
            cpars, clog = o['cpars'], o['clog']
            if not isRunActive(cpars):
                o['Start'].enable()
                o['Stop'].disable()
                o['setup'].resetSDSUhard.enable()
                o['setup'].resetSDSUsoft.enable()
                o['setup'].resetPCI.disable()
                o['setup'].setupServers.disable()
                o['setup'].powerOn.disable()
                o['setup'].powerOff.enable()
                clog.log.info('Run stopped')
                self.stop()
                return

        self.id = self.after(100, self.update)

    def stop(self):
        if self.id is not None:
            self.after_cancel(self.id)
        self.id = None

class FocalPlaneSlide(tk.LabelFrame):
    """
    Self-contained widget to deal with the focal plane slide
    """

    def __init__(self, master, share):
        """
        master  : containing widget
        """
        tk.LabelFrame.__init__(
            self, master, text='Focal plane slide',padx=10,pady=10)

        # Top for table of buttons
        top = tk.Frame(self)

        width = 8
        self.home     = tk.Button(top, fg='black', text='home',  width=width,
                                  command=lambda: self.wrap('home'))
        self.park     = tk.Button(top, fg='black', text='park',  width=width,
                                  command=lambda: self.wrap('park'))
        self.block    = tk.Button(top, fg='black', text='block', width=width,
                                 command=lambda: self.wrap('block'))

        self.gval     = IntegerEntry(top, 1100., None, True, width=4)
        self.goto     = tk.Button(top, fg='black', text='goto', width=width,
                                  command=lambda: self.wrap('goto',self.gval.value()))

        self.position = tk.Button(top, fg='black', text='position', width=width,
                                  command=lambda: self.wrap('position'))
        self.reset   = tk.Button(top, fg='black', text='reset', width=width,
                                 command=lambda: self.wrap('reset'))
        self.stop    = tk.Button(top, fg='black', text='stop', width=width,
                                 command=lambda: self.wrap('stop'))
#
#        self.enable  = tk.Button(top, fg='black', text='enable', width=width,
#                                 command=lambda: self.wrap('enable'))
#        self.disable = tk.Button(top, fg='black', text='disable', width=width,
#                                 command=lambda: self.wrap('disable'))
        self.restore = tk.Button(top, fg='black', text='restore', width=width,
                                 command=lambda: self.wrap('restore'))

        self.home.grid(row=0,column=0)
        self.park.grid(row=0,column=1)
        self.block.grid(row=0,column=2)

        self.goto.grid(row=1,column=0)
        self.gval.grid(row=1,column=1)
        self.position.grid(row=1,column=2)
        self.reset.grid(row=2,column=0)
#
#        self.enable.grid(row=2,column=0)
#        self.disable.grid(row=2,column=1)
        self.restore.grid(row=2,column=1)
        self.stop.grid(row=2,column=2)

        top.pack(pady=5)

        # make a region to display results of
        # slide commands
        bot = tk.Frame(self)
        scrollbar = tk.Scrollbar(bot)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        console = tk.Text(bot, height=6, width=40, bg=COL['log'],
                          yscrollcommand=scrollbar.set)
        console.configure(state=tk.DISABLED)
        console.pack(side=tk.LEFT)
        scrollbar.config(command=console.yview)

        # make a handler for GUIs
        ltgh = LoggingToGUI(console)

        # define the formatting
        #        logging.Formatter.converter = time.gmtime
        formatter = logging.Formatter('%(message)s')
        ltgh.setFormatter(formatter)

        # make a logger and set the handler
        self.log = logging.getLogger('Slide log')
        self.log.addHandler(ltgh)
        bot.pack(pady=5)

        # Finish off
        self.where   = 'UNDEF'
        self.running = False
        self.share   = share
        self.slide   = slide.Slide(self.log)

    def wrap(self, *comm):
        """
        Carries out an action wrapping it in a thread so that
        we don't have to sit around waiting for completion.
        """
        if not self.running:
            o = self.share
            cpars, clog = o['cpars'], o['clog']
            clog.log.info('Focal plane slide operation started:\n')
            clog.log.info(' '.join(comm) + '\n')
            t = threading.Thread(target=lambda: self.action(comm))
            t.daemon = True
            t.start()
            self.running = True
            self.check()
        else:
            print('a focal plane slide command is already underway')

    def action(self, comm):
        """
        Send a command to the focal plane slide
        """
        o       = self.share
        cpars   = o['cpars']

        print(comm)
        if comm[0] == 'home':
            t = threading.Thread(target=self.slide.home())
        elif comm[0] == 'park':
            t = threading.Thread(target=self.slide.park())
        elif comm[0] == 'block':
            t = threading.Thread(target=self.slide.move_absolute(-100,'px'))
        elif comm[0] == 'position':
            t = threading.Thread(target=self.slide.report_position())
        elif comm[0] == 'reset':
            t = threading.Thread(target=self.slide.reset())
        elif comm[0] == 'restore':
            t = threading.Thread(target=self.slide.restore())
        elif comm[0] == 'enable':
            t = threading.Thread(target=self.slide.enable())
        elif comm[0] == 'disable':
            t = threading.Thread(target=self.slide.disable())
        elif comm[0] == 'stop':
            t = threading.Thread(target=self.slide.stop())
        elif comm[0] == 'goto':
            if comm[1] is not None:
                t = threading.Thread(target=self.slide.move_absolute(comm[1],'px'))
            else:
                print('must enter an integer pixel position for mask first')
        else:
            print('Command = ' + str(comm) + ' not implemented yet.\n')

        self.where = comm[0]

       # flag to tell the check routine to stop
        self.running = False

    def check(self):
        """
        Check for the end of the focal plane command
        """
        if self.running:
            # check once per second
            self.after(1000, self.check)
        else:
            o       = self.share
            clog    = o['clog']
            clog.log.info('Focal plane slide operation finished\n')

class InfoFrame(tk.LabelFrame):
    """
    Information frame: run number, exposure time, etc.
    """
    def __init__(self, master, share):
        tk.LabelFrame.__init__(self, master,
                               text='Run & Tel status', padx=4, pady=4)

        self.run     = tk.Label(self, text='UNDEF')
        self.frame   = tk.Label(self,text='UNDEF')
        self.timer   = Timer(self, share)
        self.cadence = tk.Label(self,text='UNDEF')
        self.duty    = tk.Label(self,text='UNDEF')
        self.filt    = tk.Label(self,text='UNDEF')
        self.ra      = tk.Label(self,text='UNDEF')
        self.dec     = tk.Label(self,text='UNDEF')
        self.alt     = tk.Label(self,text='UNDEF')
        self.az      = tk.Label(self,text='UNDEF')
        self.airmass = tk.Label(self,text='UNDEF')
        self.ha      = tk.Label(self,text='UNDEF')
        self.pa      = tk.Label(self,text='UNDEF')
        self.engpa   = tk.Label(self,text='UNDEF')
        self.focus   = tk.Label(self,text='UNDEF')
        self.mdist   = tk.Label(self,text='UNDEF')
        self.fpslide = tk.Label(self,text='UNDEF')

        # left-hand side
        tk.Label(self,text='Run:').grid(row=0,column=0,padx=5,sticky=tk.W)
        self.run.grid(row=0,column=1,padx=5,sticky=tk.W)

        tk.Label(self,text='Frame:').grid(row=1,column=0,padx=5,sticky=tk.W)
        self.frame.grid(row=1,column=1,padx=5,sticky=tk.W)

        tk.Label(self,text='Exposure:').grid(row=2,column=0,padx=5,sticky=tk.W)
        self.timer.grid(row=2,column=1,padx=5,sticky=tk.W)

        tk.Label(self,text='Filter:').grid(row=3,column=0,padx=5,sticky=tk.W)
        self.filt.grid(row=3,column=1,padx=5,sticky=tk.W)

        tk.Label(self,text='Cadence:').grid(row=4,column=0,padx=5,sticky=tk.W)
        self.cadence.grid(row=4,column=1,padx=5,sticky=tk.W)

        tk.Label(self,text='Duty cycle:').grid(row=5,column=0,padx=5,
                                               sticky=tk.W)
        self.duty.grid(row=5,column=1,padx=5,sticky=tk.W)

        # middle
        tk.Label(self,text='RA:').grid(row=0,column=3,padx=5,sticky=tk.W)
        self.ra.grid(row=0,column=4,padx=5,sticky=tk.W)

        tk.Label(self,text='Dec:').grid(row=1,column=3,padx=5,sticky=tk.W)
        self.dec.grid(row=1,column=4,padx=5,sticky=tk.W)

        tk.Label(self,text='Alt:').grid(row=2,column=3,padx=5,sticky=tk.W)
        self.alt.grid(row=2,column=4,padx=5,sticky=tk.W)

        tk.Label(self,text='Az:').grid(row=3,column=3,padx=5,sticky=tk.W)
        self.az.grid(row=3,column=4,padx=5,sticky=tk.W)

        tk.Label(self,text='Airm:').grid(row=4,column=3,padx=5,sticky=tk.W)
        self.airmass.grid(row=4,column=4,padx=5,sticky=tk.W)

        tk.Label(self,text='HA:').grid(row=5,column=3,padx=5,sticky=tk.W)
        self.ha.grid(row=5,column=4,padx=5,sticky=tk.W)

        # right-hand side
        tk.Label(self,text='PA:').grid(row=0,column=6,padx=5,sticky=tk.W)
        self.pa.grid(row=0,column=7,padx=5,sticky=tk.W)

        # right-hand side
        tk.Label(self,text='Eng. PA:').grid(row=1,column=6,padx=5,sticky=tk.W)
        self.engpa.grid(row=1,column=7,padx=5,sticky=tk.W)

        tk.Label(self,text='Focus:').grid(row=2,column=6,padx=5,sticky=tk.W)
        self.focus.grid(row=2,column=7,padx=5,sticky=tk.W)

        tk.Label(self,text='Mdist:').grid(row=3,column=6,padx=5,sticky=tk.W)
        self.mdist.grid(row=3,column=7,padx=5,sticky=tk.W)

        tk.Label(self,text='FP slide:').grid(row=4,column=6,padx=5,sticky=tk.W)
        self.fpslide.grid(row=4,column=7,padx=5,sticky=tk.W)

        self.share = share

        # these are used to judge whether we are tracking or not
        self.ra_old    = 0.
        self.dec_old   = 0.
        self.pa_old    = 0.
        self.tracking  = False

        # start
        self.count = 0
        self.update()

    def update(self):
        """
        Updates run & tel status window. Runs
        once every 10 seconds.
        """

        o = self.share
        if 'astro' not in o:
            self.after(100, self.update)
            return

        cpars, clog, rlog, astro = o['cpars'], \
            o['clog'], o['rlog'], o['astro']

        if cpars['access_tcs']:
            if cpars['telins_name'] == 'TNO-USPEC':
                try:
                    # Poll TCS for ra,dec etc.
                    ra,dec,pa,focus,tflag,engpa = tcs.getTntTcs()

                    self.ra.configure(text=d2hms(ra/15., 1, False))
                    self.dec.configure(text=d2hms(dec, 0, True))
                    while pa < 0.:
                        pa += 360.
                    while pa > 360.:
                        pa -= 360.
                    self.pa.configure(text='{0:6.2f}'.format(pa))

                    # check for significant changes in position to flag
                    # tracking failures
                    if abs(ra-self.ra_old) < 1.e-3 and \
                            abs(dec-self.dec_old) < 1.e-3 and tflag:
                        self.tracking = True
                        self.ra.configure(bg=COL['main'])
                        self.dec.configure(bg=COL['main'])
                    else:
                        self.tracking = False
                        self.ra.configure(bg=COL['warn'])
                        self.dec.configure(bg=COL['warn'])

                    # check for changing sky PA
                    if abs(pa-self.pa_old) > 0.1 and \
                            abs(pa-self.pa_old-360.) > 0.1 and \
                            abs(pa-self.pa_old+360.) > 0.1:
                        self.pa.configure(bg=COL['warn'])
                    else:
                        self.pa.configure(bg=COL['main'])

                    # store current values for comparison with next
                    self.ra_old  = ra
                    self.dec_old = dec
                    self.pa_old  = pa

                    # set engineering PA, warn if within 20 degrees
                    # of limits
                    self.engpa.configure(text='{0:+6.1f}'.format(engpa))

                    # rotator limits are -220, +250. Warn when within 20
                    # degrees of these. (I carried out a test and the
                    # upper rotator limit was actually hit at +255 but
                    # I have stuck to 250).
                    if engpa < -200 or engpa > 230:
                        self.engpa.configure(bg=COL['warn'])
                    else:
                        self.engpa.configure(bg=COL['main'])

                    # set focus
                    self.focus.configure(text='{0:+5.2f}'.format(focus))

                    # create a Body for the target, calculate most of the stuff
                    # that we don't get from the telescope
                    star = ephem.FixedBody()
                    star._ra  = math.radians(ra)
                    star._dec = math.radians(dec)
                    star.compute(astro.obs)

                    lst = astro.obs.sidereal_time()
                    ha  = (math.degrees(lst)-ra)/15.
                    if ha > 12.:
                        ha -= 12.
                    elif ha < -12.:
                        ha += 12.
                    self.ha.configure(text=d2hms(ha, 0, True))

                    dalt = math.degrees(star.alt)
                    daz  = math.degrees(star.az)
                    self.alt.configure(text='{0:<4.1f}'.format(dalt))
                    self.az.configure(text='{0:<5.1f}'.format(daz))

                    # warn about the TV mast. Basically checks whether
                    # alt and az lie in roughly triangular shape
                    # presented by the mast. First move azimuth 5 deg closer
                    # to the mast to give a bit of warning.
                    if daz > 33.5:
                        daz = min(33.5,daz-5.)
                    else:
                        daz = max(33.5,daz+5.)

                    if daz > 25.5 and daz < 50.0 and \
                            dalt < 73.5 and \
                            ((daz < 33.5 and \
                                  dalt < 73.5-(33.5-daz)/ \
                                  (33.5-25.5)*(73.5-21.5)) or \
                                 (daz > 33.5 and \
                                      dalt < 73.5- \
                                      (daz-33.5)/(50.0-33.5)*(73.5-21.5))):
                        self.alt.configure(bg=COL['warn'])
                        self.az.configure(bg=COL['warn'])
                    else:
                        self.alt.configure(bg=COL['main'])
                        self.az.configure(bg=COL['main'])

                    # set airmass
                    self.airmass.configure(text='{0:<4.2f}'.format(
                            1./math.sin(star.alt)))

                    # distance to the moon. Warn if too close (configurable) to it.
                    md = math.degrees(ephem.separation(astro.moon,star))
                    self.mdist.configure(text='{0:<7.2f}'.format(md))
                    if md < cpars['mdist_warn']:
                        self.mdist.configure(bg=COL['warn'])
                    else:
                        self.mdist.configure(bg=COL['main'])

                    # calculate cosine of angle between vertical and celestial
                    # North cpan = (math.sin(astro.obs.lat)-math.sin(star._dec)
                    # *math.sin(star.alt))/(math.cos(star._dec)*math.cos(
                    # star.alt)) pan = math.acos(cpan)

                except Exception, err:
                    self.ra.configure(text='UNDEF')
                    self.dec.configure(text='UNDEF')
                    self.pa.configure(text='UNDEF')
                    self.ha.configure(text='UNDEF')
                    self.alt.configure(text='UNDEF')
                    self.az.configure(text='UNDEF')
                    self.airmass.configure(text='UNDEF')
                    self.mdist.configure(text='UNDEF')
                    print(err)

        if cpars['cdf_servers_on']:

            # get run number (set by the 'Start' button')
            try:
                if not isRunActive(cpars):
                    run = getRunNumber(cpars, rlog, True)
                    self.run.configure(text='{0:03d}'.format(run))

                run = int(self.run.cget('text'))
                rstr = 'run{0:03d}'.format(run)
                url = cpars['http_file_server'] + rstr + '?action=get_num_frames'
                response = urllib2.urlopen(url)
                rstr = response.read()
                ind = rstr.find('nframes="')
                if ind > -1:
                    ind += 9
                    nframe = int(rstr[ind:ind+rstr[ind:].find('"')])
                    self.frame.configure(text='{0:d}'.format(nframe))
            except Exception, err:
                clog.log.debug('Error occurred trying to set run or frame\n')
                clog.log.debug(str(err) + '\n')

        # get the current filter, if the wheel is defined
        # poll at 5x slower rate than the frame
        if 'wheel' in self.share and self.count % 5 == 0:
            wheel = self.share['wheel']
            try:
                if not wheel.connected:
                    wheel.connect()
                    wheel.init()
                findex = wheel.getPos()-1
                self.filter.configure(text=cpars['active_filter_names'][findex])
            except Exception, err:
                if self.count % 50:
                    clog.info.warn('Failed to get filter for Run & Tel\n')
                    clog.info.warn(str(err) + '\n')

        # run every 2 seconds
        self.count += 1
        self.after(2000, self.update)

class AstroFrame(tk.LabelFrame):
    """
    Astronomical information frame
    """
    def __init__(self, master, share):
        tk.LabelFrame.__init__(self, master, padx=2, pady=2, text='Time & Sky')

        # times
        self.mjd       = tk.Label(self)
        self.utc       = tk.Label(self,width=9,anchor=tk.W)
        self.lst       = tk.Label(self)

        # sun info
        self.sunalt    = tk.Label(self,width=11,anchor=tk.W)
        self.riset     = tk.Label(self)
        self.lriset    = tk.Label(self)
        self.astro     = tk.Label(self)

        # moon info
        self.moonra    = tk.Label(self)
        self.moondec   = tk.Label(self)
        self.moonalt   = tk.Label(self)
        self.moonphase = tk.Label(self)

        # observatory info
        cpars = share['cpars']
        self.obs      = ephem.Observer()

        tins = TINS[cpars['telins_name']]
        self.obs.lat       = tins['latitude']
        self.obs.lon       = tins['longitude']
        self.obs.elevation = tins['elevation']

        # generate Sun and Moon
        self.sun = ephem.Sun()
        self.moon = ephem.Moon()

        # arrange time info
        tk.Label(self,text='MJD:').grid(
            row=0,column=0,padx=2,pady=3,sticky=tk.W)
        self.mjd.grid(row=0,column=1,columnspan=2,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='UTC:').grid(
            row=0,column=3,padx=2,pady=3,sticky=tk.W)
        self.utc.grid(row=0,column=4,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='LST:').grid(
            row=0,column=5,padx=2,pady=3,sticky=tk.W)
        self.lst.grid(row=0,column=6,padx=2,pady=3,sticky=tk.W)

        # arrange solar info
        tk.Label(self,text='Sun:').grid(
            row=1,column=0,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='Alt:').grid(
            row=1,column=1,padx=2,pady=3,sticky=tk.W)
        self.sunalt.grid(row=1,column=2,padx=2,pady=3,sticky=tk.W)
        self.lriset.grid(row=1,column=3,padx=2,pady=3,sticky=tk.W)
        self.riset.grid(row=1,column=4,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='At -18:').grid(
            row=1,column=5,padx=2,pady=3,sticky=tk.W)
        self.astro.grid(row=1,column=6,padx=2,pady=3,sticky=tk.W)

        # arrange moon info
        tk.Label(self,text='Moon:').grid(
            row=2,column=0,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='RA:').grid(
            row=2,column=1,padx=2,pady=3,sticky=tk.W)
        self.moonra.grid(row=2,column=2,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='Dec:').grid(row=3,column=1,padx=2,sticky=tk.W)
        self.moondec.grid(row=3,column=2,padx=2,sticky=tk.W)
        tk.Label(self,text='Alt:').grid(
            row=2,column=3,padx=2,pady=3,sticky=tk.W)
        self.moonalt.grid(row=2,column=4,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='Phase:').grid(row=3,column=3,padx=2,sticky=tk.W)
        self.moonphase.grid(row=3,column=4,padx=2,sticky=tk.W)

        # report back to the user
        clog = share['clog']
        tins = TINS[cpars['telins_name']]
        clog.log.info('Tel/ins  = ' + cpars['telins_name'] + '\n')
        clog.log.info('Longitude = ' + tins['longitude'] + ' E\n')
        clog.log.info('Latitude   = ' + tins['latitude'] + ' N\n')
        clog.log.info('Elevation  = ' + str(tins['elevation']) + ' m\n')

        # parameters used to reduce re-calculation of sun rise etc, and
        # to provide info for other widgets
        self.lastRiset = 0
        self.lastAstro = 0
        self.counter   = 0

        # start
        self.update()

    def update(self):
        """
        Updates @ 10Hz to give smooth running clock.
        """
        # current time in seconds since start of UNIX
        utc = time.time()
        self.obs.date = ephem.Date(UNIX0-EPH0+utc/DAY)

        # configure times
        self.utc.configure(text=time.strftime('%H:%M:%S',time.gmtime(utc)))
        self.mjd.configure(text='{0:11.5f}'.format(UNIX0-MJD0+utc/DAY))
        lst = DAY*(self.obs.sidereal_time()/math.pi/2.)
        self.lst.configure(text=time.strftime('%H:%M:%S',time.gmtime(lst)))

        if self.counter % 100 == 0:
            # only re-compute Sun & Moon info once every 100 calls

            # re-compute sun
            self.obs.pressure = 1010.
            self.sun.compute(self.obs)

            self.sunalt.configure(\
                text='{0:+03d} deg'.format(
                    int(round(math.degrees(self.sun.alt)))))

            if self.obs.date > self.lastRiset and \
                    self.obs.date > self.lastAstro:
                # Only re-compute rise and setting times when necessary,
                # and only re-compute when both rise/set and astro twilight
                # times have gone by

                # turn off refraction for both sunrise & set and astro
                # twilight calculation.
                self.obs.pressure = 0.

                # For sunrise and set we set the horizon down to match
                # a standard amount of refraction at the horizon
                self.obs.horizon  = '-0:34'
                sunset  = self.obs.next_setting(self.sun)
                sunrise = self.obs.next_rising(self.sun)

                # Astro twilight: geometric centre at -18 deg
                self.obs.horizon = '-18'
                astroset  = self.obs.next_setting(self.sun, use_center=True)
                astrorise = self.obs.next_rising(self.sun, use_center=True)

                if sunrise > sunset:
                    # In the day time we report the upcoming sunset and
                    # end of evening twilight
                    self.lriset.configure(text='Sets:')
                    self.lastRiset = sunset
                    self.lastAstro = astroset

                elif astrorise > astroset and astrorise < sunrise:
                    # During evening twilight, we report the sunset just
                    # passed and end of evening twilight
                    self.lriset.configure(text='Sets:')
                    self.obs.horizon  = '-0:34'
                    self.lastRiset = self.obs.previous_setting(self.sun)
                    self.lastAstro = astroset

                elif astrorise > astroset and astrorise < sunrise:
                    # During night, report upcoming start of morning
                    # twilight and sunrise
                    self.lriset.configure(text='Rises:')
                    self.obs.horizon  = '-0:34'
                    self.lastRiset = sunrise
                    self.lastAstro = astrorise

                else:
                    # During morning twilight report start of twilight
                    # just passed and upcoming sunrise
                    self.lriset.configure(text='Rises:')
                    self.obs.horizon  = '-18'
                    self.lastRiset = sunrise
                    self.lastAstro = self.obs.previous_rising(
                        self.sun, use_center=True)

                # Configure the corresponding text fields
                ntime = DAY*(self.lastRiset + EPH0 - UNIX0)
                self.riset.configure(
                    text=time.strftime('%H:%M:%S',time.gmtime(ntime)))
                ntime = DAY*(self.lastAstro + EPH0 - UNIX0)
                self.astro.configure(
                    text=time.strftime('%H:%M:%S',time.gmtime(ntime)))

                # re-compute moon
                self.obs.pressure = 1010.
                self.moon.compute(self.obs)
                self.moonra.configure(text='{0}'.format(self.moon.ra))
                self.moondec.configure(text='{0}'.format(self.moon.dec))
                self.moonalt.configure(\
                    text='{0:+03d} deg'.format(
                        int(round(math.degrees(self.moon.alt)))))
                self.moonphase.configure(\
                    text='{0:02d} %'.format(
                        int(round(100.*self.moon.moon_phase))))

        # update counter
        self.counter += 1

        # run again after 100 milli-seconds
        self.after(100, self.update)


# various helper routines

def isRunActive(cpars):
    """
    Polls the data server to see if a run is active
    """
    if cpars['cdf_servers_on']:
        url = cpars['http_data_server'] + 'status'
        response = urllib2.urlopen(url, timeout=2)
        rs  = ReadServer(response.read())
        if not rs.ok:
            raise DriverError('isRunActive error: ' + str(rs.err))

        if rs.state == 'IDLE':
            return False
        elif rs.state == 'BUSY':
            return True
        else:
            raise DriverError('isRunActive error, state = ' + rs.state)
    else:
        raise DriverError('isRunActive error: cdf_servers_on = False')

def getRunNumber(cpars, rlog, nocheck=False):
    """
    Polls the data server to find the current run number. Throws
    exceptions if it can't determine it.

    cpars : dictionary of configuration parameters

    nocheck : determines whether a check for an active run is made
            nocheck=False is safe, but runs 'isRunActive' which
            might not be needed if you have called this already.
            nocheck=True avoids the isRunActive but runs the risk
            of polling for the run of an active run which cannot
            be done.
    """

    if not cpars['cdf_servers_on']:
        raise DriverError('getRunNumber error: cdf_servers_on is set to False')

    if nocheck or isRunActive(cpars):
        url = cpars['http_data_server'] + 'fstatus'
        response = urllib2.urlopen(url)
        rs  = ReadServer(response.read())
        if rs.ok:
            return rs.run
        else:
            raise DriverError('getRunNumber error: ' + str(rs.err))
    else:
        raise DriverError('getRunNumber error')

def checkSimbad(target, maxobj=5):
    """
    Sends off a request to Simbad to check whether a target is recognised.
    Returns with a list of results.
    """
    url   = 'http://simbad.u-strasbg.fr/simbad/sim-script'
    q     = 'set limit ' + str(maxobj) + \
        '\nformat object form1 "Target: %IDLIST(1) | %COO(A D;ICRS)"\nquery ' \
        + target
    query = urllib.urlencode({'submit' : 'submit script', 'script' : q})
    resp  = urllib2.urlopen(url, query)
    data  = False
    error = False
    results = []
    for line in resp:
        if line.startswith('::data::'):
            data = True
        if line.startswith('::error::'):
            error = True
        if data and line.startswith('Target:'):
            name,coords = line[7:].split(' | ')
            results.append(
                {'Name' : name.strip(), 'Position' : coords.strip(),
                 'Frame' : 'ICRS'})
    resp.close()

    if error and len(results):
        print('drivers.check: Simbad: there appear to be some ' + \
                  'results but an error was unexpectedly raised.')
    return results


class WinPairs (tk.Frame):
    """
    Class to define a frame of multiple window pairs,
    contained within a gridded block that can be easily position.
    """

    def __init__(self, master, xsls, xslmins, xslmaxs, xsrs, xsrmins, xsrmaxs,
                 yss, ysmins, ysmaxs, nxs, nys, xbfac, ybfac, checker):
        """
        Arguments:

          master :
            container widget

          xsls, xslmins, xslmaxs :
            initial X values of the leftmost columns of left-hand windows
            along with minimum and maximum values (array-like)

          xsrs, xsrmins, xsrmaxs :
            initial X values of the leftmost column of right-hand windows
            along with minimum and maximum values (array-like)

          yss, ysmins, ysmaxs :
            initial Y values of the lowest row of the window
            along with minimum and maximum values (array-like)

          nxs :
            X dimensions of windows, unbinned pixels
            (array-like)

          nys :
            Y dimensions of windows, unbinned pixels
            (array-like)

          xbfac :
            array of unique x-binning factors

          ybfac :
            array of unique y-binning factors

          checker :
            checker function to provide a global check and update in response
            to any changes made to the values stored in a Window. Can be None.

        It is assumed that the maximum X dimension is the same for both left
        and right windows and equal to xslmax-xslmin+1.
        """

        npair = len(xsls)
        checks = (xsls, xslmins, xslmaxs, xsrs, xsrmins, xsrmaxs, \
                      yss, ysmins, ysmaxs, nxs, nys)
        for check in checks:
            if npair != len(check):
                raise DriverError(
                    'drivers.WindowPairs.__init__:' + \
                        ' conflict array lengths amonst inputs')

        tk.Frame.__init__(self, master)

        # top part contains the binning factors and
        # the number of active windows
        top = tk.Frame(self)
        top.pack(anchor=tk.W)

        tk.Label(top, text='Binning factors (X x Y): ').grid(
            row=0, column=0, sticky=tk.W)

        xyframe = tk.Frame(top)
        self.xbin = ListInt(xyframe, xbfac[0], xbfac, checker, width=2)
        self.xbin.pack(side=tk.LEFT)
        tk.Label(xyframe, text=' x ').pack(side=tk.LEFT)
        self.ybin = ListInt(xyframe, ybfac[0], ybfac, checker, width=2)
        self.ybin.pack(side=tk.LEFT)
        xyframe.grid(row=0,column=1,sticky=tk.W)

        row = 1
        self.npair = RangedInt(top, 1, 1, npair, checker, False, width=2)
        if npair > 1:
            # Second row: number of windows
            tk.Label(top, text='Number of window pairs').grid(
                row=1,column=0, sticky=tk.W)
            self.npair.grid(row=row,column=1,sticky=tk.W,pady=2)
            row += 1

        # bottom part contains the window settings
        bottom = tk.Frame(self)
        bottom.pack(anchor=tk.W)

        # top row
        tk.Label(bottom, text='xsl').grid(row=row,column=1,ipady=5,sticky=tk.S)
        tk.Label(bottom, text='xsr').grid(row=row,column=2,ipady=5,sticky=tk.S)
        tk.Label(bottom, text='ys').grid(row=row,column=3,ipady=5,sticky=tk.S)
        tk.Label(bottom, text='nx').grid(row=row,column=4,ipady=5,sticky=tk.S)
        tk.Label(bottom, text='ny').grid(row=row,column=5,ipady=5,sticky=tk.S)

        row += 1
        self.label, self.xsl, self.xsr, self.ys, self.nx, self.ny = \
            [],[],[],[],[],[]
        nr = 0
        for xsl, xslmin, xslmax, xsr, xsrmin, xsrmax, ys, ysmin, ysmax, \
                nx, ny in zip(*checks):

            # create
            if npair == 1:
                self.label.append(tk.Label(bottom, text='Pair: '))
            else:
                self.label.append(
                    tk.Label(bottom, text='Pair ' + str(nr) + ': '))

            self.xsl.append(
                RangedInt(bottom, xsl, xslmin, xslmax, checker, True, width=4))
            self.xsr.append(
                RangedInt(bottom, xsr, xsrmin, xsrmax, checker, True, width=4))
            self.ys.append(
                RangedInt(bottom, ys, ysmin, ysmax, checker, True, width=4))
            self.nx.append(
                RangedMint(bottom, nx, 1, xslmax-xslmin+1, self.xbin,
                           checker, True, width=4))
            self.ny.append(
                RangedMint(bottom, ny, 1, ysmax-ysmin+1, self.ybin,
                           checker, True, width=4))

            # arrange
            self.label[-1].grid(row=row,column=0)
            self.xsl[-1].grid(row=row,column=1)
            self.xsr[-1].grid(row=row,column=2)
            self.ys[-1].grid(row=row,column=3)
            self.nx[-1].grid(row=row,column=4)
            self.ny[-1].grid(row=row,column=5)

            row += 1
            nr  += 1

        # syncing button
        self.sbutt = ActButton(bottom, 5, {}, self.sync, text='Sync')
        self.sbutt.grid(row=row,column=0,columnspan=5,pady=10,sticky=tk.W)
        self.frozen = False

    def check(self):
        """
        Checks the values of the window pairs. If any problems are found, it
        flags them by changing the background colour.

        Returns (status, synced)

          status : flag for whether parameters are viable at all
          synced : flag for whether the windows are synchronised.
        """

        status = True
        synced = False

        xbin  = self.xbin.value()
        ybin  = self.ybin.value()
        npair = self.npair.value()

        # individual pair checks
        for xslw, xsrw, ysw, nxw, nyw in \
                zip(self.xsl[:npair], self.xsr[:npair], self.ys[:npair],
                    self.nx[:npair], self.ny[:npair]):
            xslw.config(bg=COL['main'])
            xsrw.config(bg=COL['main'])
            ysw.config(bg=COL['main'])
            nxw.config(bg=COL['main'])
            nyw.config(bg=COL['main'])
            status = status if xslw.ok() else False
            status = status if xsrw.ok() else False
            status = status if ysw.ok() else False
            status = status if nxw.ok() else False
            status = status if nyw.ok() else False
            xsl = xslw.value()
            xsr = xsrw.value()
            ys  = ysw.value()
            nx  = nxw.value()
            ny  = nyw.value()

            # Are unbinned dimensions consistent with binning factors?
            if nx is None or nx % xbin != 0:
                nxw.config(bg=COL['error'])
                status = False

            if ny is None or ny % ybin != 0:
                nyw.config(bg=COL['error'])
                status = False

            # overlap checks
            if xsl is None or xsr is None or xsl >= xsr:
                xsrw.config(bg=COL['error'])
                status = False

            if xsl is None or xsr is None or nx is None or xsl + nx > xsr:
                xsrw.config(bg=COL['error'])
                status = False

            # Are the windows synchronised? This means that they would
            # be consistent with the pixels generated were the whole CCD
            # to be binned by the same factors. If relevant values are not
            # set, we count that as "synced" because the purpose of this is
            # to enable / disable the sync button and we don't want it to be
            # enabled just because xs or ys are not set.
            synced = True if xsl is None or xsr is None or \
                ys is None or nx is None or ny is None or \
                ((xsl - 1) % xbin == 0 and (xsr - 1) % xbin == 0 \
                     and (ys - 1) % ybin == 0) else synced

            # Range checks
            if xsl is None or nx is None or xsl + nx - 1 > xslw.imax:
                xslw.config(bg=COL['error'])
                status = False

            if xsr is None or nx is None or xsr + nx - 1 > xsrw.imax:
                xsrw.config(bg=COL['error'])
                status = False

            if ys is None or ny is None or ys + ny - 1 > ysw.imax:
                ysw.config(bg=COL['error'])
                status = False

        # Pair overlap checks. Compare one pair with the next one upstream
        # (if there is one). Only bother if we have survived so far, which
        # saves a lot of checks
        if status:
            n1 = 0
            for ysw1, nyw1 in zip(self.ys[:npair-1], self.ny[:npair-1]):

                ys1  = ysw1.value()
                ny1  = nyw1.value()

                n1 += 1

                ysw2, nyw2 = self.ys[n1], self.ny[n1]

                ys2  = ysw2.value()
                ny2  = nyw2.value()

                if ys1 + ny1 > ys2:
                    ysw2.config(bg=COL['error'])
                    status = False

        if synced:
            self.sbutt.config(bg=COL['main'])
            self.sbutt.disable()
        else:
            if not self.frozen:
                self.sbutt.enable()
            self.sbutt.config(bg=COL['warn'])

        return status

    def enable(self):
        npair = self.npair.value()
        for label, xsl, xsr, ys, nx, ny in \
                zip(self.label[:npair], self.xsl[:npair], self.xsr[:npair],
                    self.ys[:npair], self.nx[:npair], self.ny[:npair]):
            label.config(state='normal')
            xsl.enable()
            xsr.enable()
            ys.enable()
            nx.enable()
            ny.enable()

        for label, xsl, xsr, ys, nx, ny in \
                zip(self.label[npair:], self.xsl[npair:], self.xsr[npair:],
                    self.ys[npair:], self.nx[npair:], self.ny[npair:]):
            label.config(state='disable')
            xsl.disable()
            xsr.disable()
            ys.disable()
            nx.disable()
            ny.disable()

    def disable(self):
        for label, xsl, xsr, ys, nx, ny in \
                zip(self.label, self.xsl, self.xsr, self.ys, self.nx, self.ny):
            label.config(state='disable')
            xsl.disable()
            xsr.disable()
            ys.disable()
            nx.disable()
            ny.disable()

    def sync(self):
        """
        Synchronise the settings. This means that the pixel start
        values are shifted downwards so that they are synchronised
        with a full-frame binned version. This does nothing if the
        binning factors == 1.
        """

        # needs some mods for ultracam ??
        xbin = self.xbin.value()
        ybin = self.ybin.value()
        n = 0
        for xsl, xsr, ys, nx, ny in self:
            if xbin > 1:
                if xsl % xbin != 1:
                    xsl = xbin*((xsl-1)//xbin)+1
                    self.xsl[n].set(xsl)
                if xsr % xbin != 1:
                    xsr = xbin*((xsr-1)//xbin)+1
                    self.xsr[n].set(xsr)

            if ybin > 1 and ys % ybin != 1:
                ys = ybin*((ys-1)//ybin)+1
                self.ys[n].set(ys)

            n += 1
        self.sbutt.config(state='disable')

    def freeze(self):
        """
        Freeze all settings so they can't be altered
        """
        for xsl, xsr, ys, nx, ny in \
                zip(self.xsl, self.xsr,
                    self.ys, self.nx, self.ny):
            xsl.disable()
            xsr.disable()
            ys.disable()
            nx.disable()
            ny.disable()
        self.sbutt.config(state='disable')
        self.frozen = True

    def unfreeze(self):
        """
        Unfreeze all settings
        """
        npair = self.npair.value()
        for label, xsl, xsr, ys, nx, ny in \
                zip(self.label[:npair], self.xsl[:npair], self.xsr[:npair],
                    self.ys[:npair], self.nx[:npair], self.ny[:npair]):
            label.config(state='normal')
            xsl.enable()
            xsr.enable()
            ys.enable()
            nx.enable()
            ny.enable()

        for label, xsl, xsr, ys, nx, ny in \
                zip(self.label[npair:], self.xsl[npair:], self.xsr[npair:],
                    self.ys[npair:], self.nx[npair:], self.ny[npair:]):
            label.config(state='disable')
            xsl.disable()
            xsr.disable()
            ys.disable()
            nx.disable()
            ny.disable()

        self.frozen = False
        self.check()

    def __iter__(self):
        """
        Generator to allow looping through through the window pairs.
        Successive calls return xsl, xsr, ys, nx, ny for each pair
        """
        n = 0
        npair = self.npair.value()
        while n < npair:
            yield (self.xsl[n].value(),self.xsr[n].value(),
                   self.ys[n].value(),self.nx[n].value(),self.ny[n].value())
            n += 1

class Windows (tk.Frame):
    """
    Class to define a frame of multiple windows as a gridded
    block that can be placed easily within a container widget.
    Also defines binning factors and the number of active windows.
    """

    def __init__(self, master, xss, xsmins, xsmaxs, yss, ysmins, ysmaxs,
                 nxs, nys, xbfac, ybfac, checker):
        """
        Arguments:

          master :
            container widget

          xss, xsmins, xsmaxs :
            initial X values of the leftmost column of window(s)
            along with minimum and maximum values (array-like)

          yss, ysmins, ysmaxs :
            initial Y values of the lowest row of the window
            along with minimum and maximum values (array-like)

          nxs :
            initial X dimensions of windows, unbinned pixels
            (array-like)

          nys :
            initial Y dimension(s) of windows, unbinned pixels
            (array-like)

          xbfac :
            set of x-binning factors

          ybfac :
            set of y-binning factors

          checker :
            checker function to provide a global check and update in response
            to any changes made to the values stored in a Window. Can be None.
        """

        nwin = len(xss)
        checks = (xss, xsmins, xsmaxs, yss, ysmins, ysmaxs, nxs, nys)
        for check in checks:
            if nwin != len(check):
                raise DriverError('drivers.Windows.__init__: ' + \
                                      'conflict array lengths amonst inputs')

        tk.Frame.__init__(self, master)

        # top part contains the binning factors and the number
        # of active windows
        top = tk.Frame(self)
        top.pack(anchor=tk.W)

        tk.Label(top, text='Binning factors (X x Y): ').grid(
            row=0, column=0, sticky=tk.W)

        xyframe = tk.Frame(top)
        self.xbin = ListInt(xyframe, xbfac[0], xbfac, checker, width=2)
        self.xbin.pack(side=tk.LEFT)
        tk.Label(xyframe, text=' x ').pack(side=tk.LEFT)
        self.ybin = ListInt(xyframe, ybfac[0], ybfac, checker, width=2)
        self.ybin.pack(side=tk.LEFT)
        xyframe.grid(row=0,column=1,sticky=tk.W)

        # Second row: number of windows
        self.nwin = RangedInt(top, 1, 1, nwin, checker, False, width=2)
        row = 1
        if nwin > 1:
            tk.Label(top, text='Number of windows').grid(
                row=row,column=0, sticky=tk.W)
            self.nwin.grid(row=1,column=1,sticky=tk.W,pady=2)
            row += 1

        # bottom part contains the window settings
        bottom = tk.Frame(self)
        bottom.pack(anchor=tk.W)

        # top row
        tk.Label(bottom, text='xs').grid(row=row,column=1,ipady=5,sticky=tk.S)
        tk.Label(bottom, text='ys').grid(row=row,column=2,ipady=5,sticky=tk.S)
        tk.Label(bottom, text='nx').grid(row=row,column=3,ipady=5,sticky=tk.S)
        tk.Label(bottom, text='ny').grid(row=row,column=4,ipady=5,sticky=tk.S)

        print('making windows')
        self.label, self.xs, self.ys, self.nx, self.ny = [],[],[],[], []
        nr = 0
        row += 1
        for xs, xsmin, xsmax, ys, ysmin, ysmax, nx, ny in zip(*checks):

            # create
            if nwin == 1:
                self.label.append(tk.Label(bottom, text='Window: '))
            else:
                self.label.append(
                    tk.Label(bottom, text='Window ' + str(nr+1) + ': '))

            self.xs.append(
                RangedInt(bottom, xs, xsmin, xsmax, checker, True, width=4))
            self.ys.append(
                RangedInt(bottom, ys, ysmin, ysmax, checker, True, width=4))
            self.nx.append(
                RangedMint(bottom, nx, 1, xsmax-xsmin+1,
                           self.xbin, checker, True, width=4))
            self.ny.append(
                RangedMint(bottom, ny, 1, ysmax-ysmin+1,
                           self.ybin, checker, True, width=4))

            # arrange
            self.label[-1].grid(row=row,column=0)
            self.xs[-1].grid(row=row,column=1)
            self.ys[-1].grid(row=row,column=2)
            self.nx[-1].grid(row=row,column=3)
            self.ny[-1].grid(row=row,column=4)

            row += 1
            nr  += 1

        self.sbutt = ActButton(bottom, 5, {}, self.sync, text='Sync')
        self.sbutt.grid(row=row,column=0,columnspan=5,pady=6,sticky=tk.W)
        self.frozen = False

    def check(self):
        """
        Checks the values of the windows. If any problems are found,
        it flags them by changing the background colour. Only active
        windows are checked.

        Returns status, flag for whether parameters are viable.
        """
        print('checking windows')
        status = True
        synced = False

        xbin = self.xbin.value()
        ybin = self.ybin.value()
        nwin = self.nwin.value()

        # individual window checks
        for xsw, ysw, nxw, nyw in \
                zip(self.xs[:nwin], self.ys[:nwin],
                    self.nx[:nwin], self.ny[:nwin]):

            xsw.config(bg=COL['main'])
            ysw.config(bg=COL['main'])
            nxw.config(bg=COL['main'])
            nyw.config(bg=COL['main'])
            status = status if xsw.ok() else False
            status = status if ysw.ok() else False
            status = status if nxw.ok() else False
            status = status if nyw.ok() else False
            xs  = xsw.value()
            ys  = ysw.value()
            nx  = nxw.value()
            ny  = nyw.value()

            # Are unbinned dimensions consistent with binning factors?
            if nx is None or nx % xbin != 0:
                nxw.config(bg=COL['error'])
                status = False

            if ny is None or ny % ybin != 0:
                nyw.config(bg=COL['error'])
                status = False

            # Are the windows synchronised? This means that they
            # would be consistent with the pixels generated were
            # the whole CCD to be binned by the same factors
            # If relevant values are not set, we count that as
            # "synced" because the purpose of this is to enable
            # / disable the sync button and we don't want it to be
            # enabled just because xs or ys are not set.
            synced = True if \
                xs is None or ys is None or nx is None or ny is None or \
                ((xs - 1) % xbin == 0 and (ys - 1) % ybin == 0) \
                else synced

            # Range checks
            if xs is None or nx is None or xs + nx - 1 > xsw.imax:
                xsw.config(bg=COL['error'])
                status = False

            if ys is None or ny is None or ys + ny - 1 > ysw.imax:
                ysw.config(bg=COL['error'])
                status = False

        # Overlap checks. Compare each window with the next one, requiring
        # no y overlap and that the second is higher than the first
        if status:
            n1 = 0
            for ysw1, nyw1 in zip(self.ys[:nwin-1], self.ny[:nwin-1]):

                ys1  = ysw1.value()
                ny1  = nyw1.value()

                n1 += 1
                ysw2, nyw2 = self.ys[n1], self.ny[n1]

                ys2  = ysw2.value()
                ny2  = nyw2.value()

                if ys2 < ys1 + ny1:
                    ysw2.config(bg=COL['error'])
                    status = False

        print('almost checked')
        if synced:
            self.sbutt.config(bg=COL['main'])
            self.sbutt.disable()
            print('synced')
        else:
            if not self.frozen:
                self.sbutt.enable()
            self.sbutt.config(bg=COL['warn'])
            print('not synced')

        return status

    def enable(self):
        print('enabling windows')
        nwin = self.nwin.value()
        for label, xs, ys, nx, ny in \
                zip(self.label[:nwin], self.xs[:nwin], self.ys[:nwin],
                    self.nx[:nwin], self.ny[:nwin]):
            label.config(state='normal')
            xs.enable()
            ys.enable()
            nx.enable()
            ny.enable()

        for label, xs, ys, nx, ny in \
                zip(self.label[nwin:], self.xs[nwin:], self.ys[nwin:],
                    self.nx[nwin:], self.ny[nwin:]):
            label.config(state='disable')
            xs.disable()
            ys.disable()
            nx.disable()
            ny.disable()

    def disable(self):
        print('disabling windows')
        for label, xs, ys, nx, ny in \
                zip(self.label, self.xs, self.ys, self.nx, self.ny):
            label.config(state='disable')
            xs.disable()
            ys.disable()
            nx.disable()
            ny.disable()

    def sync(self, *args):
        """
        Synchronise the settings. This means that the pixel start
        values are shifted downwards so that they are synchronised
        with a full-frame binned version. This does nothing if the
        binning factor == 1
        """
        print('syncing windows ',args)
        xbin = self.xbin.value()
        ybin = self.ybin.value()
        n = 0
        for xs, ys, nx, ny in self:
            if xbin > 1 and xs % xbin != 1:
                xs = xbin*((xs-1)//xbin)+1
                self.xs[n].set(xs)

            if ybin > 1 and ys % ybin != 1:
                ys = ybin*((ys-1)//ybin)+1
                self.ys[n].set(ys)

            n += 1
        self.sbutt.config(state='disable')

    def freeze(self):
        """
        Freeze all settings so they can't be altered
        """
        for xs, ys, nx, ny in \
                zip(self.xs, self.ys, self.nx, self.ny):
            xs.disable()
            ys.disable()
            nx.disable()
            ny.disable()
        self.sbutt.config(state='disable')
        self.frozen = True

    def unfreeze(self):
        """
        Unfreeze all settings
        """
        print('unfreezing windows')
        nwin = self.nwin.value()
        for label, xs, ys, nx, ny in \
                zip(self.label[:nwin], self.xs[:nwin], self.ys[:nwin],
                    self.nx[:nwin], self.ny[:nwin]):
            label.config(state='normal')
            xs.enable()
            ys.enable()
            nx.enable()
            ny.enable()

        for label, xs, ys, nx, ny in \
                zip(self.label[nwin:], self.xs[nwin:], self.ys[nwin:],
                    self.nx[nwin:], self.ny[nwin:]):
            label.config(state='disable')
            xs.disable()
            ys.disable()
            nx.disable()
            ny.disable()

        self.frozen = False
        self.check()

    def __iter__(self):
        """
        Generator to allow looping through through the window values.
        Successive calls return xs, ys, nx, ny for each window
        """
        n = 0
        nwin = self.nwin.value()
        while n < nwin:
            yield (self.xs[n].value(),self.ys[n].value(),
                   self.nx[n].value(),self.ny[n].value())
            n += 1

def d2hms(d, decp, sign):
    """
    Converts a decimal to HH:MM:SS.SS format. Also
    appropriate for dd:mm:ss

    d    :  decimal value
    dp   :  number of decimal places for seconds
    sign :  True to add a + sign for positive d
    """
    dp = abs(d)
    h, fh = divmod(dp,1)
    m, fm = divmod(60.*fh,1)
    s = 60.*fm
    h  = int(h) if d >= 0. else -int(h)
    m  = int(m)
    ns = int(round(s))
    form = '{0:'
    if sign:
        form += '+03d'
    else:
        form += '02d'
    form += '}:{1:02d}:{2:0'
    if decp == 0:
        form += '2d}'
        if ns == 60:
            m += 1
            ns = 0
            if m == 60:
                h += 1
                m  = 0
                if h == 24:
                    h = 0
        return form.format(h,m,ns)
    else:
        form += str(3+decp) + '.' + str(decp) + 'f}'
        return form.format(h,m,s)

class DriverError(Exception):
    pass
