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
import urllib2
import logging

# may need this at some point
#proxy_support = urllib2.ProxyHandler({})
#opener = urllib2.build_opener(proxy_support)
#urllib2.install_opener(opener)

# Some standard colours

# The main overall colour for the surrounds
COL_MAIN     = '#a0d0f0'

# Background colour for the text input boxes 
# -- slightly darker version on COL_MAIN
COL_TEXT_BG  = '#80c0e0'

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

# Colours for the important start/stop action buttons.
COL_START    = '#aaffaa'
COL_STOP     = '#ffaaaa'

def loadConfPars(fp):
    """
    Loads a dictionary of configuration parameters given a file object
    pointing to the configuration file.
    """

    # read the confpars file
    parser = ConfigParser.ConfigParser()
    parser.readfp(fp)

    # intialise dictionary
    confpars = {}

    # names / types of simple single value items needing no changes.
    SINGLE_ITEMS = {'RTPLOT_SERVER_ON' : 'boolean', 'ULTRACAM_SERVERS_ON' : 'boolean', 
                    'EXPERT_MODE' : 'boolean', 'FILE_LOGGING_ON' : 'boolean', 
                    'HTTP_CAMERA_SERVER' : 'string', 'HTTP_DATA_SERVER' : 'string',
                    'APP_DIRECTORY' : 'string', 'TEMPLATE_FROM_SERVER' : 'boolean',
                    'TEMPLATE_DIRECTORY' : 'string', 'LOG_FILE_DIRECTORY' : 'string',
                    'CONFIRM_ON_CHANGE' : 'boolean', 'CONFIRM_HV_GAIN_ON' : 'boolean',
                    'OBSERVING_MODE' : 'boolean', 'TELESCOPE' : 'string', 
                    'DEBUG' : 'boolean', 'HTTP_PATH_GET' : 'string', 
                    'HTTP_PATH_EXEC' : 'string', 'HTTP_PATH_CONFIG' : 'string',
                    'HTTP_SEARCH_ATTR_NAME' : 'string'}

    for key, value in SINGLE_ITEMS.iteritems():
        if value == 'boolean':
            confpars[key.lower()] = parser.getboolean('All',key)
        elif value == 'string':
            confpars[key.lower()] = parser.get('All',key)

    # names with multiple values (all strings)
    MULTI_ITEMS = ['FILTER_NAMES', 'FILTER_IDS', 'ACTIVE_FILTER_NAMES', 'POWER_ON', 'UAC_DATABASE_HOST']

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
        self.bind('<Button-1>', lambda e : self.add(1))
        self.bind('<Button-3>', lambda e : self.sub(1))
        self.bind('<Double-Button-1>', self._dadd)
        self.bind('<Double-Button-3>', self._dsub)
        self.bind('<Shift-Button-1>', lambda e : self.add(10))
        self.bind('<Shift-Button-3>', lambda e : self.sub(10))
        self.bind('<Control-Button-1>', lambda e : self.add(100))
        self.bind('<Control-Button-3>', lambda e : self.sub(100))
        self._enter_id = self.bind('<Enter>', self._enter)
        self.bind('<Next>', lambda e : self.val.set(0))

    def _set_bind(self):
        """
        Sets key bindings -- we need this more than once
        """
        self.bind('<Button-1>', lambda e : self.add(1))
        self.bind('<Button-3>', lambda e : self.sub(1))
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
            self.get()
            return True
        except:
            return False

    # following are callbacks for bindings
    def _dadd(self, event):
        self.add(2)
        return 'break'

    def _dsub(self, event):
        self.sub(2)
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

class Application(tk.OptionMenu):

    def __init__(self, master, confpars):
        self.val = tk.StringVar()
        self.val.set(confpars['template_labels'][0])
        tk.OptionMenu.__init__(self, master, self.val, *confpars['template_labels'])

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

def saveXML(root):
    """
    Saves the current setup to disk. 

      root : (xml.etree.ElementTree.Element)
         The current setup.
    """
    print(ET.tostring(root))
    fname = tkFileDialog.asksaveasfilename(defaultextension='.xml', \
                                               filetypes=[('xml files', '.xml'),])
    if not fname: 
        print('Aborted save to disk')
        return
    tree = ET.ElementTree(root)
    print(type(root), type(tree), fname)
    tree.write(fname)
    print('Saved setup to',fname)
    
def postXML(root, confpars):
    """
    Posts the current setup to the camera and data servers.

      root : (xml.etree.ElementTree.Element)
         The current setup.
      confpars : (dict)
         Configuration parameters inc. urls of servers
    """
    if confpars['debug']:
        print('Inside postXML')

    # Write setup to an xml string
    sxml = ET.tostring(root)

    # Send the xml to the camera server
    url = confpars['http_camera_server'] + confpars['http_path_config']
    if confpars['debug']:
        print('Camera URL = ' + url)
    opener = urllib2.build_opener()
    print('content length =',len(sxml))
    req = urllib2.Request(url, data=sxml, headers={'Content-type': 'text/xml'})
    print('req')
    response = opener.open(req, timeout=5)
    print('response')
    rxml = response.read()
    csr  = ReadServer(rxml)

    # Send the xml to the data server
    url = confpars['http_data_server'] + confpars['http_path_config']
    if confpars['debug']:
        print('Data server URL = ' + url)
    req = urllib2.Request(url, data=sxml, headers={'Content-type': 'text/xml'})
    response = opener.open(req, timeout=5) # ?? need to check whether this is needed
    rxml = response.read()
    fsr  = ReadServer(rxml)

class ActButton(tk.Button):
    """
    Base class for action buttons.
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
        tk.Button.__init__(self, master, fg='black', width=width, command=self._act, **kwargs)

        self.other    = other
        self.callback = callback

    def enable(self):
        """
        Enable the button
        """
        self.configure(state='normal')

    def disable(self):
        """
        Disable the button
        """
        self.configure(state='disable')

    def _act(self):
        """
        Carry out the action associated with the button.
        This must be overridden.
        """
        return NotImplemented

class Start(ActButton):
    """
    Class defining the 'Start' button's operation
    """

    def __init__(self, master, width, other, callback):
        """
        master   : containing widget
        width    : width of button
        other    : dictionary with configuration parameters and the loggers
        callback : function which will be called with argument 'Start' after a successful use of
                   the start button.
        """
        
        ActButton.__init__(self, master, width, other, callback, bg=COL_START, text='Start')

    def _act(self):
        """
        Carries out the action associated with Start button
        """
        confpars = self.other['confpars']

        if confpars['debug']:
            print('DEBUG: Start pressed')
            print('DEBUG: Start pressed: camera server = ' + confpars['http_camera_server'])
            print('DEBUG: Start pressed: data server   = ' + confpars['http_data_server'])

        if execCommand('GO', confpars, self.other['commLogger'], self.other['respLogger']):
            self.disable()
            self.callback('Start')
        else:
            print('Failed to start a run')

class Stop(ActButton):
    """
    Class defining the 'Stop' button's operation
    """

    def __init__(self, master, width, other, callback):
        """
        master   : containing widget
        width    : width of button
        other    : dictionary with configuration parameters and the loggers
        callback : function which will be called with argument 'Stop' after a successful use of
                   the start button.
        """
        
        ActButton.__init__(self, master, width, other, callback, bg=COL_STOP, text='Stop')

    def _act(self):
        """
        Carries out the action associated with Stop button
        """
        confpars = self.other['confpars']

        if confpars['debug']:
            print('DEBUG: Stop pressed')

        if execCommand('EX,0', confpars, self.other['commLogger'], self.other['respLogger']):
            self.disable()
            self.callback('Stop')
        else:
            print('Failed to stop run')

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
    """

    def __init__(self, resp):
        print('Server response = ' + resp)
 
        # Store the entire response
        self.root = ET.fromstring(resp)

        # Identify the source: camera or filesave
        cfind = self.root.find('source')
        if not cfind:
            self.camera = None
            self.ok     = False
            self.err    = 'Could not identify source'
            self.state  = None
            return

        self.camera = cfind.text.find('Camera') > -1

        # Work out whether it was happy
        sfind = self.root.find('status')
        if not sfind:
            self.ok    = False
            self.err   = 'Could not identify status'
            self.state = None
            return

        self.ok = True
        self.err    = ''
        for key, value in sfind.attrib:
            if value != 'OK':
                self.ok  = False
                self.err = key + ' is listed as ' + value

        # Determine state of the camera
        sfind = self.root.find('state')
        if not sfind:
            self.ok     = False
            self.err    = 'Could not identify state'
            self.state  = None
            return
        self.state = sfind.attrib['server']

def execCommand(command, confpars, commLogger, respLogger):
    """
    Executes a command by sending it to the camera server

    Arguments:

      command : (string)
           the command (see below)

      confpars : (ConfPars)
           configuration parameters

      commLogger : 
           logger of commands

      respLogger : 
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
    try:
        url = confpars['http_camera_server'] + confpars['http_path_exec'] + '?' + command
        response = urllib2.urlopen(url)
        commLogger.info('Sent command ' + command)
        rs  = ReadServer(response.read())
        respLogger.info(ET.tostring(rs))
        if not rs.ok:
            print('Response from camera server not OK')
            print('Reason: ' + rs.err)
            return False

        return True
    except Exception, err:
        raise err

def execRemoteApp(app, confpars):
    """
    Executes an application stored at the server end by sending
    its name to both camera and data servers

    Arguments:

      app : (string)
           the application command (see below)

      confpars : (ConfPars)
           configuration parameters

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
    try:
        url = confpars['http_camera_server'] + confpars['http_path_exec'] + '?' + app
        if confpars['debug']:
            print('Command URL = ' + url)
        response = urllib2.urlopen(url)
        rs  = ReadServer(response.read())
        if not rs.ok:
            print('Response from camera server not OK')
            print('Reason: ' + rs.err)
            return False

        url = confpars['http_data_server'] + confpars['http_path_exec'] + '?' + app
        if confpars['debug']:
            print('Command URL = ' + url)
        response = urllib2.urlopen(url)
        rs  = ReadServer(response.read())
        if not rs.ok:
            print('Response from data server to power on was not OK')
            print('Reason: ' + rs.err)
            return False

        return True
    except Exception, err:
        raise err

class PowerOn(ActButton):
    """
    Class defining the 'Power on' button's operation
    """

    def __init__(self, master, width, other, callback):
        """
        master  : containing widget
        width   : width of button
        other   : other objects
        callback : function that will be called with argument 'Power on'
        """
        
        ActButton.__init__(self, master, width, other, callback, text='Power on')

    def _act(self):
        """
        Power on action
        """
        # shortening
        oth = self.other

        if oth['confpars']['debug']:
            print('DEBUG: Power on pressed')
            
        if execRemoteApp(oth['confpars']['power_on'], oth['confpars']) and \
                execCommand('GO', oth['confpars'], oth['commLogger'], oth['respLogger']):
            oth['observe'].post.enable()
            oth['observe'].start.disable()
            oth['observe'].stop.disable()
            self.disable()
            self.callback('Power on')

class ResetSDSUhard(ActButton):
    """
    Class defining the 'Reset SDSU hardware' button
    """

    def __init__(self, master, width, other, callback):
        """
        master   : containing widget
        width    : width of button
        other    : dictionary of other objects
        callback : function that will be called with argument 'Reset SDSU hardware'
        """
        
        ActButton.__init__(self, master, width, other, callback, text='Reset SDSU hardware')

    def _act(self):
        """
        Carries out the action associated with the Reset SDSU button
        """

        oth = self.other
        if oth['confpars']['debug']:
            print('DEBUG: Reset SDSU hardware pressed')

        if execCommand('RCO', oth['confpars'], oth['commLogger'], oth['respLogger']):
            self.disable()
            self.callback('Reset SDSU hardware')
        else:
            print('Failed to reset SDSU hardware')

class ResetSDSUsoft(ActButton):
    """
    Class defining the 'Reset SDSU software' button
    """

    def __init__(self, master, width, other, callback):
        """
        master   : containing widget
        width    : width of button
        other    : dictionary of other objects
        callback : function that will be called with argument 'Reset SDSU software'
        """
        
        ActButton.__init__(self, master, width, other, callback, text='Reset SDSU software')

    def _act(self):
        """
        Carries out the action associated with the Reset SDSU button
        """
        oth = self.other

        if oth['confpars']['debug']:
            print('DEBUG: Reset SDSU software pressed')

        if execCommand('RS', oth['confpars'], oth['commLogger'], oth['respLogger']):
            self.disable()
            self.callback('Reset SDSU software')
        else:
            print('Failed to reset SDSU software')

class ResetPCI(ActButton):
    """
    Class defining the 'Reset PCI' button
    """

    def __init__(self, master, width, other, callback):
        """
        master   : containing widget
        width    : width of button
        other    : dictionary with confpars, observe, commLogger, respLogger
        callback : function will be called with argument 'Reset PCI'
        """
        
        ActButton.__init__(self, master, width, other, callback, text='Reset PCI')

    def _act(self):
        """
        Carries out the action associated with the Reset PCI button
        """
        oth = self.other
        if oth['confpars']['debug']:
            oth['commLogger'].debug('DEBUG: Reset PCI pressed')

        if execCommand('RST', oth['confpars'], oth['commLogger'], oth['respLogger']):
            self.disable()
            self.callback('Reset PCI')
        else:
            self.commLogger.info('Failed to reset PCI')
        
class InstSetup(tk.LabelFrame):
    """
    Instrument configuration frame.
    """
    
    def __init__(self, master, other):
    
        tk.LabelFrame.__init__(self, master, text='Instrument setup', padx=10, pady=10)

        width = 15

        self.resetSDSUhard = ResetSDSUhard(self, width, other, self.check)
        row = 0
        self.resetSDSUhard.grid(row=row,column=0)

        self.resetSDSUsoft = ResetSDSUsoft(self, width, other, self.check)
        row += 1
        self.resetSDSUsoft.grid(row=row,column=0)

        self.resetPCI = ResetPCI(self, width, other, self.check)
        row += 1
        self.resetPCI.grid(row=row,column=0)

        self.powerOn = PowerOn(self, width, other, self.check)
        row += 1
        self.powerOn.grid(row=row,column=0)


    def check(self, *args):
        """
        Configure buttons when others change
        """

        if len(args):
            # various settings change according to the command
            if args[0] == 'Power on':
                self.resetSDSUhard.enable()
            elif args[0] == 'Reset SDSU hard':
                self.powerOn.disable()

class LogDisplay(tk.LabelFrame):
    """
    A simple logging console
    """

    def __init__(self, root, height, width, text, **options):
        tk.LabelFrame.__init__(self, root, text=text, **options);
        self.console = tk.Text(self, height=height, width=width)
        self.console.pack(side=tk.BOTTOM)

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

        # Disabling states so no user can write in it
        self.console.configure(state=tk.NORMAL)
        self.console.insert(tk.END, formattedMessage) #Inserting the logger message in the widget
        self.console.configure(state=tk.DISABLED)
        self.console.see(tk.END)
