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

# thirparty
import ephem

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
    'text_bg' : '#c0c0f0',  # Text background
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
        'platescale' : 0.4,       # Arcsecs/unbinned pixel
        'zerop'      : {\
            'u' : 20., # Zeropoints: mags for 1 ADU/sec
            'g' : 20.,
            'r' : 20.,
            'i' : 20.,
            'z' : 20.
            }
        },
    }

# Sky brightness, mags/sq-arsec
SKY = {\
    'd' : {'u' : 22, 'g' : 22, 'r' : 22, 'i' : 22, 'z' : 22},
    'g' : {'u' : 22, 'g' : 22, 'r' : 22, 'i' : 22, 'z' : 22},
    'b' : {'u' : 22, 'g' : 22, 'r' : 22, 'i' : 22, 'z' : 22},
    }

# Extinction per unit airmass
EXTINCTION = {'u' : 0.5, 'g' : 0.2, 'r' : 0.1, 'i' : 0.1, 'z' : 0.1}

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
        'RTPLOT_SERVER_ON' : 'boolean', 'ULTRACAM_SERVERS_ON' : 'boolean', 
        'EXPERT_LEVEL' : 'integer', 'FILE_LOGGING_ON' : 'boolean', 
        'HTTP_CAMERA_SERVER' : 'string', 'HTTP_DATA_SERVER' : 'string',
        'APP_DIRECTORY' : 'string', 'TEMPLATE_FROM_SERVER' : 'boolean',
        'TEMPLATE_DIRECTORY' : 'string', 'LOG_FILE_DIRECTORY' : 'string',
        'CONFIRM_ON_CHANGE' : 'boolean', 'CONFIRM_HV_GAIN_ON' : 'boolean',
        'RTPLOT_SERVER_PORT' : 'integer', 'DEBUG' : 'boolean', 
        'HTTP_PATH_GET' : 'string', 'HTTP_PATH_EXEC' : 'string', 
        'HTTP_PATH_CONFIG' : 'string', 'HTTP_SEARCH_ATTR_NAME' : 'string', 
        'INSTRUMENT_APP' : 'string', 'POWER_ON' : 'string', 
        'FOCAL_PLANE_SLIDE' : 'string', 'TELINS_NAME' : 'string',
        'REQUIRE_RUN_PARAMS' : 'boolean'}

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
        print('Telescope/instrument combination = ' + cpars['telins_name'] + ' not recognised.')
        print('Current possibilities are : ' + str(TINS.keys().sort()))
        print('Please fix the configuration file = ' + fp.name)
        exit(1)

    # Special code for the templates
    labels = [x.strip() for x in parser.get('All','TEMPLATE_LABELS').split(';')]
    pairs  = [int(x.strip()) for x in parser.get('All','TEMPLATE_PAIRS').split(';')]
    apps   = [x.strip() for x in parser.get('All','TEMPLATE_APPS').split(';')]
    ids    = [x.strip() for x in parser.get('All','TEMPLATE_IDS').split(';')]
    if len(pairs) != len(labels) or len(apps) != len(labels) or len(ids) != len(labels):
        print('TEMPLATE_LABELS, TEMPLATE_PAIRS, TEMPLATE_APPS and TEMPLATE_IDS must all')
        print('have the same number of items.')
        print('Please fix the configuration file = ' + fp.name)
        exit(1)

    cpars['templates'] = dict( \
        (arr[0],{'pairs' : arr[1], 'app' : arr[2], 'id' : arr[3]}) \
            for arr in zip(labels,pairs,apps,ids))

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
        self._value = str(int(ival))
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
        self._value = str(int(num))
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
            val = self.value() + num
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
        Returns integer value, if possible, None if not.
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
                              fg=COL['text'], bg=COL['text_bg'], width=width)

        # Control input behaviour.
        self.bind('<Enter>', lambda e : self.focus())

    def value(self):
        """
        Returns value.
        """
        return self.val.get()

    def ok(self):
        if self.value() == '' or self.value().isspace():
            return False
        else:
            return True

class Choice(tk.OptionMenu):
    """
    Menu choice class
    """
    def __init__(self, master, options, checker=None):
        self.val = tk.StringVar()
        self.val.set(options[0])
        tk.OptionMenu.__init__(self, master, self.val, *options)
        width = reduce(max, [len(s) for s in options])
        self.config(width=width)
        self.checker = checker
        if self.checker is not None:
            self.val.trace('w', self.checker)

    def value(self):
        return self.val.get()

    def set(self, choice):
        return self.val.set(choice)

    def disable(self):
        self.configure(state='disable')

    def enable(self):
        self.configure(state='normal')

class Radio(tk.Frame):
    """
    Left-to-right radio button class
    """
    def __init__(self, master, options, checker=None):
        tk.Frame.__init__(self, master)
        self.val = tk.StringVar()
        self.val.set(options[0])

        col = 0
        for option in options:
            tk.Radiobutton(self, text=option, variable=self.val, 
                           value=option).grid(row=0, column=col, sticky=tk.W)
            col += 1

        self.checker = checker
        if self.checker is not None:
            self.val.trace('w', self.checker)

    def value(self):
        return self.val.get()

    def set(self, choice):
        return self.val.set(choice)

    def disable(self):
        self.configure(state='disable')

    def enable(self):
        self.configure(state='normal')

class OnOff(tk.Checkbutton):
    """
    On or Off choice
    """

    def __init__(self, master, value, checker=None):
        self.val = tk.IntVar()
        self.val.set(value)
        tk.Checkbutton.__init__(self, master, variable=self.val, command=checker)

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
    return (xl2 < xl1+nx1 and xl2+nx2 > xl1 and yl2 < yl1+ny1 and yl2+ny2 > yl1)

def saveXML(root, clog):
    """
    Saves the current setup to disk. 

      root : (xml.etree.ElementTree.Element)
         The current setup.
    """
    fname = tkFileDialog.asksaveasfilename(defaultextension='.xml', \
                                               filetypes=[('xml files', '.xml'),])
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

    # Write setup to an xml string
    sxml = ET.tostring(root)

    # Send the xml to the camera server
    url = cpars['http_camera_server'] + cpars['http_path_config']
    clog.log.debug('Camera URL =',url,'\n')

    opener = urllib2.build_opener()
    clog.log.debug('content length =',len(sxml),'\n')
    req = urllib2.Request(url, data=sxml, headers={'Content-type': 'text/xml'})
    response = opener.open(req, timeout=5)
    csr  = ReadServer(response.read())
    rlog.log.warn(csr.resp() + '\n')
    if not csr.ok:
        clog.log.warn('Camera response was not OK\n')
        return False
    
    # Send the xml to the data server
    url = cpars['http_data_server'] + cpars['http_path_config']
    clog.log.debug('Data server URL =',url,'\n')
    req = urllib2.Request(url, data=sxml, headers={'Content-type': 'text/xml'})
    response = opener.open(req, timeout=5) # ?? need to check whether this is needed
    fsr  = ReadServer(response.read())
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
        tk.Button.__init__(self, master, fg='black', width=width, command=self.act, **kwargs)

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
        print('enable activity flag =',self._active)
        

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
        This must be overridden.
        """
        return NotImplemented

class Start(ActButton):
    """
    Class defining the 'Start' button's operation
    """

    def __init__(self, master, width, share):
        """
        master   : containing widget
        width    : width of button
        share    : dictionary with configuration parameters and the loggers
        """
        
        ActButton.__init__(self, master, width, share, bg=COL['start'], text='Start')

    def act(self):
        """
        Carries out the action associated with Start button
        """

        o = self.share
        cpars, ipars, clog, rlog = \
            o['cpars'], o['instpars'], o['clog'], o['rlog']

        clog.log.debug('Start pressed\n')

        if execCommand('GO', cpars, clog, rlog):
            clog.log.info('Run started\n')

            # update buttons
            self.disable()
            o['Stop'].enable()
            o['Post'].disable()
            o['Load'].disable()
            o['Unfreeze'].disable()
            o['setup'].resetSDSUhard.disable()
            o['setup'].resetSDSUsoft.disable()
            o['setup'].resetPCI.disable()
            o['setup'].setupServers.disable()
            o['setup'].powerOn.disable()
            o['setup'].powerOff.disable()

            # freeze instrument parameters
            ipars.freeze()

            # update the run number
            o['info'].currentrun.addone()

            # start the exposure timer
            o['info'].timer.start()

            return True
        else:
            clog.log.warn('Failed to start run\n')
            return False

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
        
        ActButton.__init__(self, master, width, share, bg=COL['stop'], text='Stop')

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
            o['Post'].enable()
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

        # Entry field, linked to a StringVar which is traced for any modification
        self.val    = tk.StringVar()
        self.val.trace('w', self.modver)
        self.entry  = tk.Entry(self, textvariable=self.val, fg=COL['text'], bg=COL['text_bg'], width=25)
        self.entry.bind('<Enter>', lambda e : self.entry.focus())

        # Verification button which accesses simbad to see if the target is recognised.
        self.verify = tk.Button(self, fg='black', width=8, text='Verify', bg=COL['main'], command=self.act)
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
            rlog.log.info('Found ' + str(len(ret)) + ' matches to "' + tname + '"\n')
            for entry in ret:
                rlog.log.info('Name: ' + entry['Name'] + ', position: ' + entry['Position'] + '\n')

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
        print('Server response = ' + resp)
 
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

        # Work out whether it was happy
        sfind = self.root.find('status')
        if sfind is None:
            self.ok    = False
            self.err   = 'Could not identify status'
            self.state = None
            return

        self.ok  = True
        self.err = ''
        for key, value in sfind.attrib.iteritems():
            if value != 'OK':
                self.ok  = False
                self.err = key + ' is listed as ' + value

        # Determine state of the camera
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
        sfind = self.root.find('lastfile')
        if sfind is not None:
            self.run = int(sfind.attrib['path'][:3])
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
    try:
        url = cpars['http_camera_server'] + cpars['http_path_exec'] + '?' + command
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
    print(cpars['http_camera_server'], cpars['http_path_config'], '?', app)
    if name == 'camera':
        url = cpars['http_camera_server'] + cpars['http_path_config'] + '?' + app
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
        
        ActButton.__init__(self, master, width, share, text='Reset SDSU hardware')

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
            o['observe'].post.disable()
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
        
        ActButton.__init__(self, master, width, share, text='Reset SDSU software')

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
            o['observe'].post.disable()
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
            o['observe'].post.enable()
            o['Reset SDSU hardware'].enable()
            o['Reset SDSU software'].enable()
            o['Setup server'].enable()
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
            o['observe'].post.disable()
            o['Reset SDSU hardware'].disable()
            o['Reset SDSU software'].disable()
            o['Reset PCI'].enable()
            o['Setup server'].disable()
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
                execServer('camera', cpars['instrument_app'], cpars, clog, rlog) and \
                execServer('data', tapp, cpars, clog, rlog) and \
                execServer('data', cpars['instrument_app'], cpars, cLog, rLog):
            clog.log.info('Setup servers succeeded\n')

            # alter buttons 
            self.disable()
            o['observe'].start.disable()
            o['observe'].stop.disable()
            o['observe'].post.disable()
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
            
        if execRemoteApp(cpars['power_on'], cpars, clog, rlog) and execCommand('GO', cpars, clog, rlog):
            clog.log.info('Power on successful\n')

            # change other buttons
            o['observe'].start.disable()
            o['observe'].stop.disable()
            o['observe'].post.enable()
            o['Reset SDSU hardware'].enable()
            o['Reset SDSU software'].enable()
            o['Reset PCI'].disable()
            o['Setup server'].disable()
            o['Power off'].enable()
            self.disable()

            # now check the run number -- lifted from Java code; the wait 
            # for the power on application to finish may not be needed
            n = 0
            while isRunActive() and n < 5:
                n += 1
            if isRunActive():
                clog.log.warn('Timed out waiting for power on run to de-activate; cannot initialise run number. Tell trm if this happens')
            else:
                o['info'].currentrun.set(getRunNumber())
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
        Power on action
        """
        # shortening
        o = self.share
        cpars, clog, rlog = o['cpars'], o['clog'], o['rlog']

        clog.log.debug('Power off pressed\n')
        clog.log.debug('This is a placeholder as there is no Power off application so it will fail\n')
            
        if execRemoteApp(cpars['power_off'], cpars, clog, rlog) and execCommand('GO', cpars, clog, rlog):
            clog.log.info('Powered off SDSU\n')
            self.disable()

            # alter other buttons
            o['observe'].start.disable()
            o['observe'].stop.disable()
            o['observe'].post.disable()
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
        tk.LabelFrame.__init__(self, master, text='Instrument setup', padx=10, pady=10)

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
        self.console = tk.Text(self, height=height, width=width, bg=COL['log'], yscrollcommand=scrollbar.set)
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
    Frame sub-class to switch between setup, focal plane slide and observing frames. 
    Provides radio buttons and hides / shows respective frames
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
                       value='Focal plane slide').grid(row=0, column=1, sticky=tk.W)
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
    Provides a menu to select the level of expertise wanted when interacting with a
    control GUI. This setting might be used to hide buttons for instance according to
    ste status of others, etc.
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
        SocketServer.TCPServer.__init__(self, ('localhost', port), RtplotHandler)
        self.instpars = instpars

    def run(self):
        while True:
            try:
                self.serve_forever()
            except Exception as e:
                print('RtplotServer.run', e)

class Timer(tk.Label):
    """
    Timer class. Updates every second.
    """
    def __init__(self, master):
        tk.Label.__init__(self, master, text='{0:<d} s'.format(0))
        self.id = None

    def start(self):
        """
        Starts the timer from zero
        """
        self.startTime = time.time()
        self.configure(text='{0:<d} s'.format(0))
        self.update()

    def update(self):
        """
        Updates @ 10Hz to give smooth running clock.
        """
        delta = int(round(time.time()-self.startTime))
        self.configure(text='{0:<d} s'.format(delta))
        self.id = self.after(100, self.update)

    def stop(self):
        if self.id is not None:
            self.after_cancel(self.id)
        self.id = None

class CurrentRun(tk.Label):
    """
    Run indicator checks every second with the server
    """
    def __init__(self, master, share):
        tk.Label.__init__(self, master, text='000')
        self.share = share
#        self.run()

    def set(self, rnum):
        """
        Sets the run number to rnum
        """
        self.configure(text='%03d' % (rnum,))

    def addone(self, rnum):
        """
        Adds one to the run number
        """
        self.set(int(self.get())+1)

    def run(self):
        """
        Runs the run number cheker, once per second.
        """
        o = self.share
        cpars = o['cpars']
        run = getRunNumber(cpars)
        self.configure(text='%03d' % (run,))
        self.after(1000, self.run)

class FocalPlaneSlide(tk.LabelFrame):
    """
    Self-contained widget to deal with the focal plane slide
    """

    def __init__(self, master, share):
        """
        master  : containing widget
        """
        tk.LabelFrame.__init__(self, master, text='Focal plane slide',padx=10,pady=10)
        width = 8
        self.park  = tk.Button(self, fg='black', text='Park',  width=width, 
                               command=lambda: self.wrap('park'))
        self.block = tk.Button(self, fg='black', text='Block', width=width, 
                               command=lambda: self.wrap('block'))
        self.home  = tk.Button(self, fg='black', text='Home',  width=width, 
                               command=lambda: self.wrap('home'))
        self.reset = tk.Button(self, fg='black', text='Reset', width=width, 
                               command=lambda: self.wrap('reset'))
        
        self.park.grid(row=0,column=0)
        self.block.grid(row=1,column=0)
        self.home.grid(row=0,column=1)
        self.reset.grid(row=1,column=1)
        self.where   = 'UNDEF'
        self.running = False
        self.share   = share

    def wrap(self, comm):
        """
        Carries out an action wrapping it in a thread so that 
        we don't have to sit around waiting for completion.
        """
        if not self.running:
            o = self.share
            cpars, clog = o['cpars'], o['clog']
            if comm == 'block':
                comm = 'pos=-100px'
            command = [cpars['focal_plane_slide'],comm]
            clog.log.info('Focal plane slide operation started:\n')
            clog.log.info(' '.join(command) + '\n')
            t = threading.Thread(target=lambda: self.action(comm))
            t.daemon = True
            t.start()
            self.running = True
            self.check()
        else:
            print('focal plane slide command already underway')

    def action(self, comm):
        """
        Send a command to the focal plane slide
        """
        o       = self.share
        cpars   = o['cpars']
        command = [cpars['focal_plane_slide'],comm] 

        # place command here
        time.sleep(10)
        subprocess.call(command)

        self.where = comm

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
        tk.LabelFrame.__init__(self, master, text='Run status')

        clabel = tk.Label(self,text='Current run:')
        self.currentRun = CurrentRun(self, share)

        tlabel = tk.Label(self,text='Exposure time:')
        timer = Timer(self)

        clabel.grid(row=0,column=0,padx=5,sticky=tk.W)
        self.currentRun.grid(row=0,column=1,padx=5,sticky=tk.W)

        tlabel.grid(row=1,column=0,padx=5,pady=5,sticky=tk.W)
        timer.grid(row=1,column=1,padx=5,pady=5,sticky=tk.W)


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
        tk.Label(self,text='MJD:').grid(row=0,column=0,padx=2,pady=3,sticky=tk.W)
        self.mjd.grid(row=0,column=1,columnspan=2,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='UTC:').grid(row=0,column=3,padx=2,pady=3,sticky=tk.W)
        self.utc.grid(row=0,column=4,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='LST:').grid(row=0,column=5,padx=2,pady=3,sticky=tk.W)
        self.lst.grid(row=0,column=6,padx=2,pady=3,sticky=tk.W)

        # arrange solar info
        tk.Label(self,text='Sun:').grid(row=1,column=0,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='Alt:').grid(row=1,column=1,padx=2,pady=3,sticky=tk.W)
        self.sunalt.grid(row=1,column=2,padx=2,pady=3,sticky=tk.W)
        self.lriset.grid(row=1,column=3,padx=2,pady=3,sticky=tk.W)
        self.riset.grid(row=1,column=4,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='At -18:').grid(row=1,column=5,padx=2,pady=3,sticky=tk.W)
        self.astro.grid(row=1,column=6,padx=2,pady=3,sticky=tk.W)

        # arrange moon info
        tk.Label(self,text='Moon:').grid(row=2,column=0,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='RA:').grid(row=2,column=1,padx=2,pady=3,sticky=tk.W)
        self.moonra.grid(row=2,column=2,padx=2,pady=3,sticky=tk.W)
        tk.Label(self,text='Dec:').grid(row=3,column=1,padx=2,sticky=tk.W)
        self.moondec.grid(row=3,column=2,padx=2,sticky=tk.W)
        tk.Label(self,text='Alt:').grid(row=2,column=3,padx=2,pady=3,sticky=tk.W)
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

        # parameters used to reduce re-calculation of sun rise etc.
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
                text='{0:+03d} deg'.format(int(round(math.degrees(self.sun.alt)))))

            if self.obs.date > self.lastRiset and  self.obs.date > self.lastAstro:
                # Only re-compute rise and setting times when necessary, and only
                # re-compute when both rise/set and astro twilight times have gone by

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
                    self.lastAstro = self.obs.previous_rising(self.sun, use_center=True)

                # Configure the corresponding text fields
                ntime = DAY*(self.lastRiset + EPH0 - UNIX0)
                self.riset.configure(text=time.strftime('%H:%M:%S',time.gmtime(ntime)))
                ntime = DAY*(self.lastAstro + EPH0 - UNIX0)
                self.astro.configure(text=time.strftime('%H:%M:%S',time.gmtime(ntime)))

                # re-compute moon
                self.obs.pressure = 1010.
                self.moon.compute(self.obs)
                self.moonra.configure(text='{0}'.format(self.moon.ra))
                self.moondec.configure(text='{0}'.format(self.moon.dec))
                self.moonalt.configure(\
                    text='{0:+03d} deg'.format(int(round(math.degrees(self.moon.alt)))))
                self.moonphase.configure(\
                    text='{0:02d} %'.format(int(round(100.*self.moon.moon_phase))))

        # update counter
        self.counter += 1

        # run again after 100 milli-seconds
        self.after(100, self.update)


class CountsFrame(tk.LabelFrame):
    """
    Frame for count rate estimates
    """
    def __init__(self, master, share):
        """
        master : enclosing widget
        share  : other objects. 'instpars' for timing & binning info.
        """
        tk.LabelFrame.__init__(self, master, pady=2, text='Count rate estimator')

        # entries
        self.filter    = Choice(self, ('u', 'g', 'r', 'i', 'z'))
#        self.filter    = Radio(self, ('u', 'g', 'r', 'i', 'z'))
        # need to place some restrictions on values
        self.mag       = FloatEntry(self, 18., self.update, True, width=5)
        self.seeing    = FloatEntry(self, 1.0, self.update, True, width=5)
        self.airmass   = FloatEntry(self, 1.5, self.update, True, width=5)
#        self.moon      = Choice(self, ('dark', 'grey', 'bright'))
        self.moon      = Radio(self, ('d', 'g', 'b'))

        # results
        self.peak      = tk.Label(self)
        self.total     = tk.Label(self)
        self.sky       = tk.Label(self)
        self.ston      = tk.Label(self)

        # arrange
        tk.Label(self,text='Filter:').grid(row=0,column=0,padx=5,pady=3,sticky=tk.W)
        self.filter.grid(row=0,column=1,padx=5,pady=3,sticky=tk.W)
        tk.Label(self,text='Mag:').grid(row=1,column=0,padx=5,pady=3,sticky=tk.W)
        self.mag.grid(row=1,column=1,padx=5,pady=3,sticky=tk.W)
        tk.Label(self,text='Seeing:').grid(row=2,column=0,padx=5,pady=3,sticky=tk.W)
        self.seeing.grid(row=2,column=1,padx=5,pady=3,sticky=tk.W)
        tk.Label(self,text='Airmass:').grid(row=2,column=0,padx=5,pady=3,sticky=tk.W)
        self.airmass.grid(row=2,column=1,padx=5,pady=3,sticky=tk.W)
        tk.Label(self,text='Moon:').grid(row=3,column=0,padx=5,pady=3,sticky=tk.W)
        self.moon.grid(row=3,column=1,padx=5,pady=3,sticky=tk.W)

        tk.Label(self,text='Peak:').grid(row=0,column=2,padx=5,pady=3,sticky=tk.W)
        self.peak.grid(row=0,column=3,padx=5,pady=3,sticky=tk.W)
        tk.Label(self,text='Total:').grid(row=1,column=2,padx=5,pady=3,sticky=tk.W)
        self.total.grid(row=1,column=3,padx=5,pady=3,sticky=tk.W)
        tk.Label(self,text='Sky:').grid(row=2,column=2,padx=5,pady=3,sticky=tk.W)
        self.sky.grid(row=2,column=3,padx=5,pady=3,sticky=tk.W)
        tk.Label(self,text='S-to-N:').grid(row=3,column=2,padx=5,pady=3,sticky=tk.W)
        self.ston.grid(row=3,column=3,padx=5,pady=3,sticky=tk.W)


    def update(self):
        """
        Updates values
        """
        pass

# various helper routines

def isRunActive():
    """
    Polls the data server to see if a run is active
    """
    url = cpars['http_data_server'] + 'status'
    response = urllib2.urlopen(url)
    rs  = ReadServer(response.read())
    rlog.log.debug('Data server response =\n' + rs.resp() + '\n')        
    if not rs.ok:
        raise DriverError('Active run check error: ' + str(rs.err))

    if rs.state == 'IDLE':
        return False
    elif rs.state == 'BUSY':
        return True
    else:
        raise DriverError('Active run check error, state = ' + rs.state)

def getRunNumber(cpars):
    """
    Polls the data server to find the current run number. This
    gets called often, so is designed to run silently. It therefore
    traps all errors and returns 0 if there are any problems.
    """
    try:
        url = cpars['http_data_server'] + 'fstatus'
        response = urllib2.urlopen(url)
        rs  = ReadServer(response.read())
        return rs.run if rs.ok else 0
    except:
        return 0

def checkSimbad(target, maxobj=5):
    """
    Sends off a request to Simbad to check whether a target is recognised.
    Returns with a list of results. 
    """
    url   = 'http://simbad.u-strasbg.fr/simbad/sim-script'
    q     = 'set limit ' + str(maxobj) + '\nformat object form1 "Target: %IDLIST(1) | %COO(A D;ICRS)"\nquery ' + target
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
            results.append({'Name' : name.strip(), 'Position' : coords.strip(), 'Frame' : 'ICRS'})
    resp.close()
    
    if error and len(results):
        print('drivers.check: Simbad: there appear to be some results but an error was unexpectedly raised.')
    return results

class DriverError(Exception):
    pass

