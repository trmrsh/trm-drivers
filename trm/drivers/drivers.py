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

# may need this at some point
#proxy_support = urllib2.ProxyHandler({})
#opener = urllib2.build_opener(proxy_support)
#urllib2.install_opener(opener)

# Some standard colours

# The main overall colour for the surrounds
COL_MAIN     = '#d0d0ff'

# Background colour for the text input boxes 
# -- slightly darker version on COL_MAIN
COL_TEXT_BG  = '#c0c0f0'

# Colour for text input. Darker than COL_TEXT_BG for 
# dark-on-bright style
COL_TEXT     = '#000050'

# Colour to switch text background as a warning
# of problems which won't stop actions proceeding
# but should be known about. Non-synchronised
# windows are the main example of this.
COL_WARN     = '#f0c050'

# Colour to switch text background as a warning of
# problems that will prevent actions going ahead.
COL_ERROR    = '#ffa0a0'

# Colour to switch background to to show that 
# somethin has positively worked.
COL_OK      = '#a0ffa0'

# Colours for the important start/stop action buttons.
COL_START    = '#aaffaa'
COL_STOP     = '#ffaaaa'

# colour for logger windows
COL_LOG      = '#e0d4ff'

def addStyle(root):
    """
    Styles the GUI: global fonts and colours.
    """

    # Default font
    default_font = tkFont.nametofont("TkDefaultFont")
    default_font.configure(size=10)
    root.option_add('*Font', default_font)

    # Menu font
    menu_font = tkFont.nametofont("TkMenuFont")
    menu_font.configure(size=10)
    root.option_add('*Menu.Font', menu_font)

    # Entry font
    entry_font = tkFont.nametofont("TkTextFont")
    entry_font.configure(size=10)
    root.option_add('*Entry.Font', menu_font)

    # position and size
    #    root.geometry("320x240+325+200")

    # Default colours. Note there is a difference between
    # specifying 'background' with a capital B or lowercase b
    root.option_add('*background', COL_MAIN)
    root.option_add('*HighlightBackground', COL_MAIN)
    root.config(background=COL_MAIN)

def loadConfPars(fp):
    """
    Loads a dictionary of configuration parameters given a file object
    pointing to the configuration file. The configuration file consists
    of a series of entries of the form:

    NAME : value

    It returns a dictionary of the stored parameters, with values translated
    to appropriate types. e.g. Yes/No values become boolean, etc.
    """

    # read the confpars file
    parser = ConfigParser.ConfigParser()
    parser.readfp(fp)

    # intialise dictionary
    confpars = {}

    # names / types of simple single value items needing no changes.
    SINGLE_ITEMS = {'RTPLOT_SERVER_ON' : 'boolean', 'ULTRACAM_SERVERS_ON' : 'boolean', 
                    'EXPERT_LEVEL' : 'integer', 'FILE_LOGGING_ON' : 'boolean', 
                    'HTTP_CAMERA_SERVER' : 'string', 'HTTP_DATA_SERVER' : 'string',
                    'APP_DIRECTORY' : 'string', 'TEMPLATE_FROM_SERVER' : 'boolean',
                    'TEMPLATE_DIRECTORY' : 'string', 'LOG_FILE_DIRECTORY' : 'string',
                    'CONFIRM_ON_CHANGE' : 'boolean', 'CONFIRM_HV_GAIN_ON' : 'boolean',
                    'TELESCOPE' : 'string', 'RTPLOT_SERVER_PORT' : 'integer',
                    'DEBUG' : 'boolean', 'HTTP_PATH_GET' : 'string', 
                    'HTTP_PATH_EXEC' : 'string', 'HTTP_PATH_CONFIG' : 'string',
                    'HTTP_SEARCH_ATTR_NAME' : 'string', 'TELESCOPE_APP' : 'string',
                    'INSTRUMENT_APP' : 'string', 'POWER_ON' : 'string',
                    'FOCAL_PLANE_SLIDE' : 'string'}

    for key, value in SINGLE_ITEMS.iteritems():
        if value == 'boolean':
            confpars[key.lower()] = parser.getboolean('All',key)
        elif value == 'string':
            confpars[key.lower()] = parser.get('All',key)
        elif value == 'integer':
            confpars[key.lower()] = parser.getint('All',key)

    # quick check
    if confpars['expert_level'] < 0 or confpars['expert_level'] > 2:
        print('EXPERT_LEVEL must be one of 0, 1, or 2.')
        print('Please fix the configuration file = ' + fp.name)
        exit(1)

    # names with multiple values (all strings)
    MULTI_ITEMS = ['FILTER_NAMES', 'FILTER_IDS', 'ACTIVE_FILTER_NAMES', 'UAC_DATABASE_HOST']

    for item in MULTI_ITEMS:
        confpars[item.lower()] = [x.strip() for x in parser.get('All',item).split(';')]

    # Run a check on the filters
    if not set(confpars['active_filter_names']) <= set(confpars['filter_names']):
        print('One or more of the active filter names was not recognised.')
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
    confpars['templates'] = dict((arr[0],{'pairs' : arr[1], 'app' : arr[2], 'id' : arr[3]}) \
                                     for arr in zip(labels,pairs,apps,ids))
    # Next line is so that we know the order defined in the file
    confpars['template_labels'] = labels
            
    return confpars

class PosInt (tk.Entry):
    """
    Provide positive or 0 integer input. This traps invalid characters
    (except for a blank field). Various key bindings define the feel
    of the entry field:

     mouse entry : sets the focus
     left-click  : add 1
     right-click : subtracts 1
     left-click + shift: adds 10
     right-click + shift: subtracts 10
     left-click + ctrl: adds 100
     right-click + ctrl: subtracts 100

    The entry value can be "traced" with a checking functions that runs
    every time anything changes.
    """

    def __init__(self, master, ival, checker, **kw):
        """
        master  : 
           the widget this gets placed inside

        ival    : 
           initial value

        checker : 
           checker function to provide a global check and update in response
           to any changes made to the PosInt value. Can be None. Should have 
           arguments *args because it is derived from setting a trace on an 
           internal IntVar
        """

        # save the checker routine
        self.checker = checker
                                
        # Define an intvar for tracing content changes
        self.val = tk.IntVar()
        self.val.set(ival)
        if self.checker is not None:
            self.val.trace('w', self.checker)

        # register an input validation command to restrict range of input
        vcmd = (master.register(self.validate), '%d', '%i', '%P', '%s', '%S', '%v', '%V', '%W')
        tk.Entry.__init__(self, master, validate='key', validatecommand=vcmd, \
                              textvariable=self.val, fg=COL_TEXT, bg=COL_TEXT_BG, \
                              **kw)

        # Control input behaviour.
        self._set_bind()

    def _set_bind(self):
        """
        Sets key bindings -- we need this more than once
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
        self.bind('<Next>', lambda e : self.val.set(0))

    def _set_unbind(self):
        """
        Unsets key bindings -- we need this more than once
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
        self.unbind('<Next>')

    def enable(self):
        self.configure(state='normal')
        self._set_bind()

    def disable(self):
        self.configure(state='disable')
        self._set_unbind()

    def validate(self, action, index, value_if_allowed,
                 prior_value, text, validation_type, trigger_type, widget_name):
        """
        Ensures only 01234567890 can be entered. It checks whether
        the combination of allowed characters is valid but just flags
        it through the colour.
        """
        if set(text) <= set('0123456789'):
            try:
                int(value_if_allowed)
                self.config(bg=COL_TEXT_BG)
            except ValueError:
                self.config(bg=COL_ERROR)
            return True
        else:
            return False

    def get(self):
        """
        Returns integer value, if possible, None if not.
        """
        try:
            return self.val.get()
        except:
            return None

    def set(self, num):
        """
        Sets the current value equal to num
        """
        self.val.set(num)

    def add(self, num):
        """
        Adds num to the current value
        """
        try:
            val = self.get() + num
        except:
            val = num
        self.set(max(0,val))

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        try:
            val = self.get() - num
        except:
            val = -num
        self.set(max(0,val))

    def ok(self):
        try:
            self.val.get()
            return True
        except:
            return False

    # following are callbacks for bindings
    def _dadd(self, event):
        self.add(1)
        return 'break'

    def _dsub(self, event):
        self.sub(1)
        return 'break'

    def _enter(self, event):
#        if self.checker is not None:
#            self.checker()
        self.focus()
        self.icursor(tk.END)

class RangedPosInt (PosInt):
    """
    This is the same as PosInt but adds a check on the range of allowed integers.
    """

    def __init__(self, master, ival, imin, imax, checker, **kw):
        # the order here is important because of the 
        # registration of validate I suspect.
        self.imin = imin
        self.imax = imax
        PosInt.__init__(self, master, ival, checker, **kw)
        self.unbind('<Next>')
        self.bind('<Next>', lambda e : self.val.set(self.imin))
        self.bind('<Prior>', lambda e : self.val.set(self.imax))

    def _set_bind(self):
        """
        Sets key bindings -- we need this more than once
        """
        PosInt._set_bind(self)
        self.unbind('<Next>')
        self.bind('<Next>', lambda e : self.val.set(self.imin))
        self.bind('<Prior>', lambda e : self.val.set(self.imax))

    def validate(self, action, index, value_if_allowed,
                 prior_value, text, validation_type, trigger_type, widget_name):
        """
        Adds range checking. Out of range numbers can be entered (otherwise it can
        make data entry irritating), but they will be flagged by colour.
        """
        if not PosInt.validate(self, action, index, value_if_allowed,
                               prior_value, text, validation_type, trigger_type, widget_name):
            return False

        try:
            v = int(value_if_allowed)
            if v >= self.imin and v <= self.imax:
                self.config(bg=COL_TEXT_BG)
            else:
                self.config(bg=COL_ERROR)
        except:
            pass
        return True

    def add(self, num):
        """
        Adds num to the current value, forcing the result to be within
        range.
        """
        try:
            val = self.get() + num
        except:
            val = num
        val = max(self.imin, min(self.imax, val))
        self.set(val)

    def sub(self, num):
        """
        Subtracts num from the current value, forcing the result to be within
        range.
        """
        try:
            val = self.get() - num
        except:
            val = -num
        val = max(self.imin, min(self.imax, val))
        self.set(val)

    def ok(self):
        if not PosInt.ok(self):
            return False

        v = self.get()
        return v >= self.imin and v <= self.imax

class RangedPosMInt (RangedPosInt):
    """
    This is the same as RangePosInt but locks to multiplesadds a check on the range of allowed integers.
    """

    def __init__(self, master, ival, imin, imax, mfac, checker, **kw):
        """
        mfac must be class that support 'get()' to return an integer value.
        """
        RangedPosInt.__init__(self, master, ival, imin, imax, checker, **kw)
        self.mfac = mfac
        self.unbind('<Next>')
        self.unbind('<Prior>')
        self.bind('<Next>', lambda e: self.val.set(self._min()))
        self.bind('<Prior>', lambda e: self.val.set(self._max()))

    def _set_bind(self):
        """
        Sets key bindings -- we need this more than once
        """
        RangedPosInt._set_bind(self)
        self.unbind('<Next>')
        self.unbind('<Prior>')
        self.bind('<Next>', lambda e: self.val.set(self._min()))
        self.bind('<Prior>', lambda e: self.val.set(self._max()))

    def _min(self):
        chunk = self.mfac.get()
        mval  = chunk*(self.imin // chunk)
        print(chunk,mval,self.imin,mval+chunk if mval < self.imin else mval)
        return mval+chunk if mval < self.imin else mval

    def _max(self):
        chunk = self.mfac.get()
        return chunk*(self.imax // chunk)

    def add(self, num):
        """
        Adds num to the current value, jumping up the next
        multiple of mfac if the result is not a multiple already
        range.
        """ 
        try:
            val = self.get() + num
        except:
            val = num

        chunk = self.mfac.get()
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
            val = self.get() - num
        except:
            val = -num

        chunk = self.mfac.get()
        if val % chunk > 0: 
            if num > 0:
                val = chunk*(val // chunk)
            elif num < 0:
                val = chunk*(val // chunk + 1)

        val = max(self._min(), min(self._max(), val))
        self.set(val)

        val = max(self.imin, min(self.imax, val))
        self.set(val)

    def ok(self):
        if not PosInt.ok(self):
            return False

        v = self.get()
        return v >= self.imin and v <= self.imax

class TextEntry (tk.Entry):
    """
    Sub-class of Entry for basic text input. Not a lot to
    it but it keeps things neater and it has a check for 
    blank entries.
    """

    def __init__(self, master, **kw):
        """
        master  : the widget this gets placed inside
        """

        # Define a StringVar
        self.val = tk.StringVar()

        tk.Entry.__init__(self, master, textvariable=self.val, \
                              fg=COL_TEXT, bg=COL_TEXT_BG, **kw)

        # Control input behaviour.
        self.bind('<Enter>', lambda e : self.focus())

    def get(self):
        """
        Returns value.
        """
        return self.val.get()

    def ok(self):
        if self.get() == '' or self.get().isblank():
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

    def get(self):
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

def saveXML(root, commLog):
    """
    Saves the current setup to disk. 

      root : (xml.etree.ElementTree.Element)
         The current setup.
    """
    fname = tkFileDialog.asksaveasfilename(defaultextension='.xml', \
                                               filetypes=[('xml files', '.xml'),])
    if not fname: 
        commLog.log.warn('Aborted save to disk\n')
        return
    tree = ET.ElementTree(root)
    tree.write(fname)
    commLog.log.info('Saved setup to',fname,'\n')
    
def postXML(root, confpars, commLog, respLog):
    """
    Posts the current setup to the camera and data servers.

      root : (xml.etree.ElementTree.Element)
         The current setup.
      confpars : (dict)
         Configuration parameters inc. urls of servers
    """
    commLog.log.debug('Entering postXML\n')

    # Write setup to an xml string
    sxml = ET.tostring(root)

    # Send the xml to the camera server
    url = confpars['http_camera_server'] + confpars['http_path_config']
    commLog.log.debug('Camera URL =',url,'\n')

    opener = urllib2.build_opener()
    commLog.log.debug('content length =',len(sxml),'\n')
    req = urllib2.Request(url, data=sxml, headers={'Content-type': 'text/xml'})
    response = opener.open(req, timeout=5)
    rxml = response.read()
    csr  = ReadServer(rxml)

    # Send the xml to the data server
    url = confpars['http_data_server'] + confpars['http_path_config']
    commLog.log.debug('Data server URL =',url,'\n')
    req = urllib2.Request(url, data=sxml, headers={'Content-type': 'text/xml'})
    response = opener.open(req, timeout=5) # ?? need to check whether this is needed
    rxml = response.read()
    fsr  = ReadServer(rxml)

    commLog.log.debug('Leaving postXML\n')

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

    def __init__(self, master, width, other, callback=None, **kwargs):
        """
        master   : containing widget
        width    : width in characters of the button
        other    : dictionary of other objects that might need to be accessed
        callback : callback function
        bg       : background colour
        kwargs   : keyword arguments
        """
        tk.Button.__init__(self, master, fg='black', width=width, command=self.act, **kwargs)

        # store some attributes. other anc calbback are obvious. 
        # _active indicates whether the button should be enabled or disabled 
        # _expert indicates whether the activity state should be overridden so
        #         that the button is enabled in any case (if set True)
        self.other    = other
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

    def __init__(self, master, width, other):
        """
        master   : containing widget
        width    : width of button
        other    : dictionary with configuration parameters and the loggers
        """
        
        ActButton.__init__(self, master, width, other, bg=COL_START, text='Start')

    def act(self):
        """
        Carries out the action associated with Start button
        """

        o = self.other
        cpars, ipars, clog, rlog = \
            o['confpars'], o['instpars'], o['commLog'], o['respLog']

        clog.log.debug('Start pressed\n')

        if execCommand('GO', cpars, clog, rlog):
            clog.log.info('Run started\n')
            self.disable()
            o['Stop'].enable()
            ipars.freeze()
            o['info'].timer.start()
            return True
        else:
            clog.log.warn('Failed to start run\n')
            return False

class Stop(ActButton):
    """
    Class defining the 'Stop' button's operation
    """

    def __init__(self, master, width, other):
        """
        master   : containing widget
        width    : width of button
        other    : dictionary with configuration parameters and the loggers
        """
        
        ActButton.__init__(self, master, width, other, bg=COL_STOP, text='Stop')

    def act(self):
        """
        Carries out the action associated with Stop button
        """

        o = self.other
        cpars, clog, rlog = o['confpars'], o['commLog'], o['respLog']

        clog.log.debug('Stop pressed\n')

        if execCommand('EX,0', cpars, clog, rlog):
            clog.log.info('Run stopped\n')
            self.disable()
            o['Start'].enable()
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
    def __init__(self, master, other):
        tk.Frame.__init__(self, master)

        # Entry field, linked to a StringVar which is traced for any modification
        self.val    = tk.StringVar()
        self.val.trace('w', self.modver)
        self.entry  = tk.Entry(self, textvariable=self.val, fg=COL_TEXT, bg=COL_TEXT_BG, width=25)
        self.entry.bind('<Enter>', lambda e : self.entry.focus())

        # Verification button which accesses simbad to see if the target is recognised.
        self.verify = tk.Button(self, fg='black', width=8, text='Verify', bg=COL_MAIN, command=self.act)
        self.entry.pack(side=tk.LEFT,anchor=tk.W)
        self.verify.pack(side=tk.LEFT,anchor=tk.W,padx=5)
        self.verify.config(state='disable')
        self.other  = other

    def get(self):
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
            self.verify.config(bg=COL_MAIN)
            self.verify.config(state='normal')
        else:
            self.verify.config(bg=COL_MAIN)
            self.verify.config(state='disable')

    def act(self):
        """
        Carries out the action associated with Verify button
        """

        o = self.other
        clog, rlog = o['commLog'], o['respLog']
        tname = self.val.get()

        clog.log.debug('Checking "' + tname + '" with simbad\n')
        ret = checkSimbad(tname)
        if len(ret) == 0:
            self.verify.config(bg=COL_ERROR)
            clog.log.warn('No matches to "' + tname + '" found\n')
        else:
            self.verify.config(bg=COL_MAIN)
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

def execCommand(command, confpars, commLog, respLog):
    """
    Executes a command by sending it to the camera server

    Arguments:

      command : (string)
           the command (see below)

      confpars : (ConfPars)
           configuration parameters

      commLog : 
           logger of commands

      respLog : 
           logger of responses

    Possible commands are:

      GO   : starts a run
      ST   : stops a run
      RCO  : resets the timing board
      RST  : resets the PCI board
      EX,0 : stops a run
      SRS  :

    Returns True/False according to whether the command
    succeeded or not.
    """

    url = confpars['http_camera_server'] + confpars['http_path_exec'] + '?' + command
    response = urllib2.urlopen(url)
    commLog.log.info('execCommand, command = "' + command + '"\n')
    rs  = ReadServer(response.read())
    respLog.log.debug(rs.ok,rs.camera,rs.state,rs.err,'\n')
    if not rs.ok:
        commLog.warn.info('Response from camera server was not OK\n')
        commLog.warn.info('Reason: ' + rs.err + '\n')
        return False

    respLog.log.info('Camera response =\n' + rs.resp() + '\n')        
    return True

def execServer(name, app, confpars, commLog, respLog):
    """
    Sends application to a server

    Arguments:

      name : (string)
         'camera' or 'data' for the camera or data server

      app : (string)
           the appication name

      confpars : (ConfPars)
           configuration parameters

      commLog :
          command log

      respLog :
          response log
          
    Returns True/False according to success or otherwise
    """
    print(confpars['http_camera_server'], confpars['http_path_config'], '?', app)
    if name == 'camera':
        url = confpars['http_camera_server'] + confpars['http_path_config'] + '?' + app
    elif name == 'data':
        url = confpars['http_data_server'] + confpars['http_path_config'] + '?' + app
    else:
        raise Exception('Server name = ' + name + ' not recognised.')
    
    commLog.log.debug('execServer, url = ' + url + '\n')

    response = urllib2.urlopen(url)
    rs  = ReadServer(response.read())
    if not rs.ok:
        commLog.log.warn('Response from ' + name + ' server not OK\n')
        commLog.log.warn('Reason: ' + rs.err + '\n')
        return False

    commLog.log.debug('execServer command was successful\n')
    return True

def execRemoteApp(app, confpars, commLog, respLog):
    """
    Executes a remote application by sending it first to the
    camera and then to the data server.

    Arguments:

      app : (string)
           the application command (see below)

      confpars : (ConfPars)
           configuration parameters

      commLog :
          command log

      respLog :
          response log

    Returns True/False according to whether the command
    succeeded or not.
    """

    return execServer('camera', app, confpars, commLog, respLog) and \
        execServer('data', app, confpars, commLog, respLog)

class ResetSDSUhard(ActButton):
    """
    Class defining the 'Reset SDSU hardware' button
    """

    def __init__(self, master, width, other):
        """
        master   : containing widget
        width    : width of button
        other    : dictionary of other objects
        """
        
        ActButton.__init__(self, master, width, other, text='Reset SDSU hardware')

    def act(self):
        """
        Carries out the action associated with the Reset SDSU hardware button
        """

        o = self.other
        cpars, clog, rlog = o['confpars'], o['commLog'], o['respLog']

        clog.log.debug('Reset SDSU hardware pressed\n')

        if execCommand('RCO', cpars, clog, rlog):
            clog.log.info('Reset SDSU hardware succeeded\n')
            self.disable()

            # adjust other buttons
            o['Reset PCI'].enable()
            o['Setup servers'].disable()
            o['Power on'].disable()
            o['observe'].start.disable()
            o['observe'].stop.disable()
            o['observe'].post.disable()
            return True
        else:
            clog.log.warn('Reset SDSU hardware failed\n')
            return False

class ResetSDSUsoft(ActButton):
    """
    Class defining the 'Reset SDSU software' button
    """

    def __init__(self, master, width, other):
        """
        master   : containing widget
        width    : width of button
        other    : dictionary of other objects
        """
        
        ActButton.__init__(self, master, width, other, text='Reset SDSU software')

    def act(self):
        """
        Carries out the action associated with the Reset SDSU software button
        """

        o = self.other
        cpars, clog, rlog = o['confpars'], o['commLog'], o['respLog']

        clog.log.debug('Reset SDSU software pressed\n')

        if execCommand('RS', cpars, clog, rlog):
            clog.log.info('Reset SDSU software succeeded\n')
            self.disable()
            # alter other buttons ??

            return True
        else:
            clog.log.warn('Reset SDSU software failed\n')
            return False

class ResetPCI(ActButton):
    """
    Class defining the 'Reset PCI' button
    """

    def __init__(self, master, width, other):
        """
        master   : containing widget
        width    : width of button
        other    : dictionary with confpars, observe, commLog, respLog
        """
        
        ActButton.__init__(self, master, width, other, text='Reset PCI')

    def act(self):
        """
        Carries out the action associated with the Reset PCI button
        """
        o = self.other
        cpars, clog, rlog = o['confpars'], o['commLog'], o['respLog']

        clog.log.debug('Reset PCI pressed\n')

        if execCommand('RST', cpars, clog, rlog):
            clog.log.info('Reset PCI succeeded\n')
            self.disable()

            # alter other buttons
            o['observe'].start.disable()
            o['observe'].stop.disable()
            o['observe'].post.enable()
            o['Reset SDSU hardware'].enable()
            o['Reset SDSU software'].enable()
            o['Setup server'].enable()
            o['Power on'].disable()
            return True
        else:
            clog.log.warn('Reset PCI failed\n')
            return False

class SystemReset(ActButton):
    """
    Class defining the 'System Reset' button
    """

    def __init__(self, master, width, other):
        """
        master   : containing widget
        width    : width of button
        other    : dictionary with confpars, observe, commLog, respLog
        """
        
        ActButton.__init__(self, master, width, other, text='System Reset')

    def act(self):
        """
        Carries out the action associated with the System Reset
        """
        o = self.other
        cpars, clog, rlog = o['confpars'], o['commLog'], o['respLog']

        clog.log.debug('System Reset pressed\n')

        if execCommand('SRS', cpars, clog, rlog):
            clog.log.info('System Reset succeeded\n')
            self.disable()
            # alter buttons here ??
            return True
        else:
            clog.log.warn('System Reset failed\n')
            return False

class SetupServers(ActButton):
    """
    Class defining the 'Setup servers' button
    """

    def __init__(self, master, width, other):
        """
        master   : containing widget
        width    : width of button
        other    : dictionary with confpars, observe, commLog, respLog
        """
        
        ActButton.__init__(self, master, width, other, text='Setup servers')

    def act(self):
        """
        Carries out the action associated with the 'Setup servers' button
        """
        o = self.other
        cpars, clog, rlog = o['confpars'], o['commLog'], o['respLog']

        clog.log.debug('Setup servers pressed\n')

        if execServer('camera', cpars['telescope_app'], cpars, clog, rlog) and \
                execServer('camera', cpars['instrument_app'], cpars, clog, rlog) and \
                execServer('data', cpars['telescope_app'], cpars, clog, rlog) and \
                execServer('data', cpars['instrument_app'], cpars, cLog, rLog):
            clog.log.info('Setup servers succeeded\n')
            self.disable()

            # alter other buttons 
            o['observe'].start.disable()
            o['observe'].stop.disable()
            o['observe'].post.disable()
            o['Reset SDSU hardware'].enable()
            o['Reset PCI'].disable()
            o['Power on'].enable()

            return True
        else:
            clog.log.warn('Setup servers failed\n')
            return False

class PowerOn(ActButton):
    """
    Class defining the 'Power on' button's operation
    """

    def __init__(self, master, width, other):
        """
        master  : containing widget
        width   : width of button
        other   : other objects
        """
        
        ActButton.__init__(self, master, width, other, text='Power on')

    def act(self):
        """
        Power on action
        """
        # shortening
        o = self.other
        cpars, clog, rlog = o['confpars'], o['commLog'], o['respLog']

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
            return True
        else:
            clog.log.warn('Power on failed\n')
            return False

class PowerOff(ActButton):
    """
    Class defining the 'Power off' button's operation
    """

    def __init__(self, master, width, other):
        """
        master  : containing widget
        width   : width of button
        other   : other objects
        """
        
        ActButton.__init__(self, master, width, other, text='Power off')
        self.disable()

    def act(self):
        """
        Power on action
        """
        # shortening
        o = self.other
        cpars, clog, rlog = o['confpars'], o['commLog'], o['respLog']

        clog.log.debug('Power off pressed\n')
        clog.log.debug('This is a placeholder as there is no Power off application so it will fail\n')
            
        if execRemoteApp(cpars['power_off'], cpars, clog, rlog) and execCommand('GO', cpars, clog, rlog):
            clog.log.info('Power off successful\n')
            self.disable()

            # alter other buttons ??
            o['observe'].post.disable()
            o['observe'].start.disable()
            o['observe'].stop.disable()
            return True
        else:
            clog.log.warn('Power off failed\n')
            return False


class Initialise(ActButton):
    """
    Class defining the 'Initialise' button's operation
    """

    def __init__(self, master, width, other):
        """
        master  : containing widget
        width   : width of button
        other   : other objects
        """
        
        ActButton.__init__(self, master, width, other, text='Initialise')

    def act(self):
        """
        Initialise action
        """
        # shortening
        o = self.other
        cpars, clog, rlog = o['confpars'], o['commLog'], o['respLog']
        
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
    
    def __init__(self, master, other):
        """
        master -- containing widget
        other  -- dictionary of other objects that this needs to access
        """
        tk.LabelFrame.__init__(self, master, text='Instrument setup', padx=10, pady=10)

        # Define all buttons
        width = 15
        self.resetSDSUhard = ResetSDSUhard(self, width, other)
        self.resetSDSUsoft = ResetSDSUsoft(self, width, other)
        self.resetPCI      = ResetPCI(self, width, other)
        self.systemReset   = SystemReset(self, width, other)
        self.setupServers  = SetupServers(self, width, other)
        self.powerOn       = PowerOn(self, width, other)
        self.initialise    = Initialise(self, width, other)
        width = 8
        self.powerOff      = PowerOff(self, width, other)

        # share all the buttons
        other['Reset SDSU hardware'] = self.resetSDSUhard
        other['Reset SDSU software'] = self.resetSDSUsoft
        other['Reset PCI']           = self.resetPCI
        other['System reset']        = self.systemReset
        other['Setup servers']       = self.setupServers
        other['Initialise']          = self.initialise
        other['Power on']            = self.powerOn
        other['Power off']           = self.powerOff

        # save
        self.other = other

        # set which buttons are presented and where they go
        self.setExpertLevel(other['confpars']['expert_level'])
        
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

    def emit(self, message): 
        """
        Overwrites the default handler's emit method:
        
        message : the message to display
        """
        formattedMessage = self.format(message)

        # Write n=message to console
        self.console.configure(state=tk.NORMAL)
        self.console.insert(tk.END, formattedMessage) 
        
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
        self.console = tk.Text(self, height=height, width=width, bg=COL_LOG, yscrollcommand=scrollbar.set)
        self.console.configure(state=tk.DISABLED)
        self.console.pack(side=tk.LEFT)
        scrollbar.config(command=self.console.yview)

        # make a handler for GUIs
        ltgh = LoggingToGUI(self.console)

        # define the formatting
        logging.Formatter.converter = time.gmtime
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s','%H:%M:%S')
        ltgh.setFormatter(formatter)

        # make a logger and set the handler
        self.log = logging.getLogger(text)
        self.log.addHandler(ltgh)

        
class Switch(tk.Frame):
    """
    Frame sub-class to switch between setup, focal plane slide and observing frames. 
    Provides radio buttons and hides / shows respective frames
    """
    def __init__(self, master, setup, fpslide, observe):
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
        
        self.observe = observe
        self.fpslide  = fpslide
        self.setup   = setup

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
    def __init__(self, master, confpars, *args):
        """
        master   -- the containing widget, e.g. toolbar menu
        confpars -- configuration parameters containing expert_level which is
                    is used to store initial value and to pass changed value
        args     -- other objects that have a 'setExpertLevel(elevel)' method.
        """
        tk.Menu.__init__(self, master, tearoff=0)
        
        self.val = tk.IntVar()
        self.val.set(confpars['expert_level'])
        self.val.trace('w', self._change)
        self.add_radiobutton(label='Level 0', value=0, variable=self.val)
        self.add_radiobutton(label='Level 1', value=1, variable=self.val)
        self.add_radiobutton(label='Level 2', value=2, variable=self.val)

        self.confpars = confpars
        self.args = args

    def _change(self, *args):
        elevel = self.val.get()
        self.confpars['expert_level'] = elevel
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
        tk.Label.__init__(self, master, text='    0')
        self.id = None

    def start(self):
        """
        Starts the timer from zero
        """
        self.startTime = time.time()
        self.configure(text='%5d' % (0,))
        self.tick()

    def tick(self):
        """
        Implements the ticks. Updates the integer number of seconds
        10 times/second.
        """
        delta = int(round(time.time()-self.startTime))
        self.configure(text='%5d' % (delta,))
        self.id = self.after(100, self.tick)

    def stop(self):
        if self.id is not None:
            self.after_cancel(self.id)
        self.id = None

class CurrentRun(tk.Label):
    """
    Run indicator checks every second with the server
    """
    def __init__(self, master, other):
        tk.Label.__init__(self, master, text='000')
        self.other = other
        self.run()

    def run(self):
        """
        Runs the run number cheker, once per second.
        """
        o = self.other
        cpars = o['confpars']
        run = getRunNumber(cpars)
        self.configure(text='%03d' % (run,))
        self.after(1000, self.run)

class FocalPlaneSlide(tk.LabelFrame):
    """
    Self-contained widget to deal with the focal plane slide
    """

    def __init__(self, master, other):
        """
        master  : containing widget
        """
        tk.LabelFrame.__init__(self, master, text='Focal plane slide',padx=10,pady=10)
        width = 8
        self.park  = tk.Button(self, fg='black', text='Park',  width=width, command=lambda: self.wrap('park'))
        self.block = tk.Button(self, fg='black', text='Block', width=width, command=lambda: self.wrap('block'))
        self.home  = tk.Button(self, fg='black', text='Home',  width=width, command=lambda: self.wrap('home'))
        self.reset = tk.Button(self, fg='black', text='Reset', width=width, command=lambda: self.wrap('reset'))
        
        self.park.grid(row=0,column=0)
        self.block.grid(row=1,column=0)
        self.home.grid(row=0,column=1)
        self.reset.grid(row=1,column=1)
        self.where   = 'UNDEF'
        self.running = False
        self.other   = other

    def wrap(self, comm):
        """
        Carries out an action wrapping it in a thread so that 
        we don't have to sit around waiting for completion.
        """
        if not self.running:
            o = self.other
            cpars, clog = o['confpars'], o['commLog']
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
        o       = self.other
        cpars   = o['confpars']
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
            o       = self.other
            clog    = o['commLog']
            clog.log.info('Focal plane slide operation finished\n')

class InfoFrame(tk.LabelFrame):
    """
    Information frame: run number, exposure time, etc.
    """
    def __init__(self, master, other):
        tk.LabelFrame.__init__(self, master, text='Current status')
        tlabel = tk.Label(self,text='Exposure time:')
        timer  = Timer(self)
        clabel = tk.Label(self,text='Current run:')
        currentRun = CurrentRun(self, other)
        
        tlabel.grid(row=0,column=0,padx=5,sticky=tk.W)
        timer.grid(row=0,column=1,padx=5,sticky=tk.W)
        tk.Label(self,text='secs').grid(row=0,column=2,padx=5,sticky=tk.W)
        clabel.grid(row=1,column=0,padx=5,sticky=tk.W)
        currentRun.grid(row=1,column=1,padx=5,sticky=tk.W)

# various helper routines

def isRunActive():
    """
    Polls the data server to see if a run is active
    """
    url = confpars['http_data_server'] + 'status'
    response = urllib2.urlopen(url)
    rs  = ReadServer(response.read())
    respLog.log.debug('Data server response =\n' + rs.resp() + '\n')        
    if not rs.ok:
        raise DriverError('Active run check error: ' + str(rs.err))

    if rs.state == 'IDLE':
        return False
    elif rs.state == 'BUSY':
        return True
    else:
        raise DriverError('Active run check error, state = ' + rs.state)

def getRunNumber(confpars):
    """
    Polls the data server to find the current run number. This
    gets called often, so is designed to run silently. It therefore
    traps all errors and returns 0 if there are any problems.
    """
    try:
        url = confpars['http_data_server'] + 'fstatus'
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

