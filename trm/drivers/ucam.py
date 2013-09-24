#!/usr/bin/env python

"""
Python module supplying classes for instrument driver
GUIs. The basic idea is to define container classes which
correspond to many of the items of the GUI. This part 
contains items of generic use to multiple drivers.
"""

from __future__ import print_function
import Tkinter as tk
import tkFont
import ConfigParser
#import xml.dom.minidom
import xml.etree.ElementTree as ET
import os
import re

class WindowPair (object):
    """
    Needs work this; half-done at the the mo'

    Class to display the settings of a symmetric WindowPair as used by
    ULTRACAM allowing the user to change them.
    """

    def __init__(self, master, row, column, ystart, xleft, xright, nx, ny, checker):
        """
        Sets up a window pair as a row of values, initialised to
        the arguments supplied. The row is created within a sub-frame
        of master.

        Arguments:

          master
            master widget within which the Frame containing the values
            will be placed. A grid layout will be adopted to allow
            other WindowPairs to abutted nicely, hence the row and
            column of the leftmost entry field must be specified

          row
            row along which values will be placed

          column
            first column for fields

          ystart
            initial Y value of the lowest row of the window pair

          xleft
            initial X value of left-hand window

          xright
            initial X value of right-hand window

          nx
            X dimension of windows, unbinned pixels

          ny
            Y dimension of windows, unbinned pixels

          checker
            validation routine
        """

        # A pair of windows needs 5 parameters to specify it:
        #
        #  ystart -- first y value to be read, same for each window
        #  xleft  -- leftmost x pixel of lefthand window
        #  xright -- leftmost x pixel of righthand window
        #  nx     -- X dimension, unbinned pixels
        #  ny     -- Y dimension, unbinned pixels

        self.ystart = RangedPosInt(master, ystart, 1, 1024, checker, width=4)
        self.ystart.grid(row=row,column=column)

        self.xleft = RangedPosInt(master, xleft, 1, 512, checker, width=4)
        self.xleft.grid(row=row,column=column+1)

        self.xright = RangedPosInt(master, xright, 513, 1024, checker, width=4)
        self.xright.grid(row=row,column=column+2)

        self.nx = RangedPosInt(master, nx, 1, 512, checker, width=4)
        self.nx.grid(row=row,column=column+3)

        self.ny = RangedPosInt(master, ny, 1, 1024, checker, width=4)
        self.ny.grid(row=row,column=column+4)

    def get(self):
        "Returns current ystart,xleft,xright,nx,ny values"
        return (self.ystart.value(),self.xleft.value(),self.xright.value(),
                self.nx.value(),self.ny.value())

    def check(self):
        """
        Checks the values of a WindowPair. If any problems are found, it flags them in red.
        Returns True / False for ok / not ok.
        """

        # get values
        ystart, xleft, xright, nx, ny = self.get()

        # are they all OK individually?
        ok = self.ystart.ok() and self.xleft.ok() and self.xright.ok() and \
            self.nx.ok() and self.ny.ok()

        # now come cross-value checks:

        # is rightmost pixel of lefthand window within range
        if xleft is None or xleft + nx - 1 > 512:
            self.xleft.config(bg=COL_WARN)
            ok = False

        # is rightmost pixel of righthand window within range
        if xright is None or xright + nx - 1 > 1024:
            self.xright.config(bg=COL_WARN)
            ok = False

        # is top pixel within range
        if ystart is None or ystart + ny - 1 > 1024:
            self.ystart.config(bg=COL_WARN)
            ok = False

        if ok:
            # set all OK is everything checks
            self.ystart.config(bg=COL_TEXT_BG)
            self.xleft.config(bg=COL_TEXT_BG)
            self.xright.config(bg=COL_TEXT_BG)
            self.nx.config(bg=COL_TEXT_BG)
            self.ny.config(bg=COL_TEXT_BG)
            
        return ok

class InstPars(tk.LabelFrame):
    """
    Ultracam instrument parameters block. Needs more work

    Following attributes are set:

      appLab : (OptionMenu)
         choice of application

      read : (OptionMenu)
         choice of readout speed

      expose : (PosInt)
         exposure delay in millseconds.


    """
        
    def __init__(self, master, config):
        tk.LabelFrame.__init__(self, master, text='Instrument setup', padx=10, pady=10)

        row     = 0
        column  = 0
        tk.Label(self, text='Application').grid(row=row,column=column,sticky=tk.W)

        row += 1
        tk.Label(self, text='Readout speed').grid(row=row,column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='Exposure delay (msecs)  ').grid(row=row,column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='No. exposures').grid(row=row,column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='Binning factors (X x Y)').grid(row=row,column=column, sticky=tk.W)

        row += 1
        wrow_start = row
        tk.Label(self, text='Windows').grid(row=row,column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='Pair 1').grid(row=row,column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='Pair 2').grid(row=row,column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='Pair 3').grid(row=row,column=column, sticky=tk.W)

        # application selection
        row     = 0
        column  = 1
        self.appLab = Application(self, config)
        self.appLab.grid(row=row,column=column,columnspan=5,sticky=tk.W)

        # readout speed
        row += 1
        self.read_val = tk.StringVar()
        options = ['Slow', 'Fast']
        self.read_val.set(options[0])
        self.read = tk.OptionMenu(self, self.read_val, *options)
        self.read.grid(row=row,column=column,columnspan=5,sticky=tk.W)

        # exposure delay
        row += 1
        self.expose = PosInt(self, 0, None, width=6)
        self.expose.grid(row=row,column=column,columnspan=5,sticky=tk.W, pady=5)

        # number of exposures
        row += 1
        self.number = PosInt(self, 1, None, width=6)
        self.number.grid(row=row,column=column,columnspan=5,sticky=tk.W, pady=5)

        row += 1
        xyframe = tk.Frame(self)
        self.xbin = RangedPosInt(xyframe, 1, 1, 8, None, width=2)
        self.xbin.pack(side=tk.LEFT)

        tk.Label(xyframe, text=' x ').pack(side=tk.LEFT)

        self.ybin = RangedPosInt(xyframe, 1, 1, 8, None, width=2)
        self.ybin.pack(side=tk.LEFT)

        xyframe.grid(row=row,column=column,columnspan=5,sticky=tk.W,pady=5)

        # window parameter names
        row = wrow_start
        tk.Label(self, text="ystart").grid(row=row,column=column)
        tk.Label(self, text="xleft").grid(row=row,column=column+1)
        tk.Label(self, text="xright").grid(row=row,column=column+2)
        tk.Label(self, text="nx").grid(row=row,column=column+3)
        tk.Label(self, text="ny").grid(row=row,column=column+4)

        # window parameter entry fields
        self.winps = []

        row += 1
        self.winps.append(WindowPair(self,  row, column, 2,   1, 513, 100, 100, self.check))

        row += 1
        self.winps.append(WindowPair(self, row, column, 201, 100, 601, 100, 100, self.check))

        row += 1
        self.winps.append(WindowPair(self, row, column, 201, 100, 601, 100, 100, self.check))

        row += 1
        # need to pack the next two buttons into a frame to present as a single 
        # item to the grid manager
        bframe = tk.Frame(self)
        self.unfreeze = tk.Button(bframe, text="Unfreeze", fg="black", \
                                      command=lambda : print('you have pressed the unfreeze button'))
        self.unfreeze.pack(side=tk.LEFT)

        self.sync = tk.Button(bframe, text="Sync", fg="black", \
                                  command=lambda : print('you have pressed the sync button'))
        self.sync.pack(side=tk.LEFT)
        bframe.grid(row=row,column=column,columnspan=5, sticky=tk.W, pady=5)


        self.check()

    def check(self):
        """
        Checks the validity of the parameters.
        """

        ok = True

        # check that each pair is ok on its own
        for winp in self.winps:
            if not winp.check():
                ok = False

        # check that no pairs overlap in the Y direction
        ystart0,xleft0,xright0,nx0,ny0 = self.winps[0].get()
        for winp in self.winps[1:]:
            ystart1,xleft1,xright1,nx1,ny1 = winp.get()
            if ystart0 is not None and ystart1 is not None and ny0 is not None and \
                    ystart1 < ystart0 + ny0:
                winp.ystart.config(bg=COL_WARN)
                ok = False
            ystart0,xleft0,xright0,nx0,ny0 = ystart1,xleft1,xright1,nx1,ny1

        return ok

class UserPars(tk.LabelFrame):
    """
    Generic parameters required from the user
    """
        
    def __init__(self, master):
        tk.LabelFrame.__init__(self, master, text='Run setup', padx=10, pady=10)

        row     = 0
        column  = 0
        tk.Label(self, text='Target name').grid(row=row,column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='Pre-run comment').grid(row=row,column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='Run type').grid(row=row,column=column, sticky=tk.W+tk.N)

        row += 1
        tk.Label(self, text='Programme ID').grid(row=row,column=column, sticky=tk.W)
            
        row += 1
        tk.Label(self, text='Principal Investigator').grid(row=row,column=column, sticky=tk.W)
            
        row += 1
        tk.Label(self, text='Observer(s)').grid(row=row,column=column, sticky=tk.W)
            
        # spacer
        column += 1
        tk.Label(self, text=' ').grid(row=0,column=column)

        # target
        row     = 0
        column += 1
        self.target = TextEntry(self, width=30)
        self.target.grid(row=row, column=column, sticky=tk.W)

        # comment
        row += 1
        self.comment = TextEntry(self, width=30)
        self.comment.grid(row=row, column=column, sticky=tk.W)

        # data types
        row += 1
        DTYPES = ('acquisition','science','bias','flat','dark','technical')
    
        self.dtype = tk.StringVar()
        self.dtype.set('acquisition') 
    
        dtframe = tk.Frame(self)
        r, c = 0, 0
        for dtype in DTYPES:
            b = tk.Radiobutton(dtframe, text=dtype, variable=self.dtype, value=dtype)
            b.grid(row=r, column=c, sticky=tk.W)
            r += 1
            if r == 2:
                r  = 0
                c += 1
        dtframe.grid(row=row,column=column,sticky=tk.W)

        # programme ID
        row += 1
        self.progid = TextEntry(self, width=20)
        self.progid.grid(row=row, column=column, sticky=tk.W)

#        row += 1
#        self.progid = TextEntry(self, width=20)
#        self.progid.grid(row=row, column=column, sticky=tk.W)

        # principal investigator
        row += 1
        self.pi = TextEntry(self, width=20)
        self.pi.grid(row=row, column=column, sticky=tk.W)

        # observers
        row += 1
        self.observers = TextEntry(self, width=20)
        self.observers.grid(row=row, column=column, sticky=tk.W)

    def check(self):
        """
        Checks the validity of the parameters. The arguments come because
        this is passed down to trace set on the integer fields
        """

        if not self.target.ok():
            return False

        if not self.progid.ok():
            return False

        if not self.prinapp.ok():
            return False

        if not self.observers.ok():
            return False

        return True

# Action section: first the action buttons 
# are defined, then the container frame for them.

def createXML(config, ccdpars, userpars):
    """
    This creates the XML representing the current setup. It does
    this by loading a template xml file using directives in the
    configuration parameters, and then imposing the current settings

    Arguments:

      config   : configuration parameters
      ccdpars  : windows etc
      userpars : target, PI nam,e etc.

    Returns xml.etree.ElementTree
    """

    # identify the template
    appLab = ccdpars.appLab.value()
    if config.debug:
        print('DEBUG: createXML: application = ' + appLab)
        print('DEBUG: createXML: application vals = ' + str(config.templates[appLab]))

    if config.template_from_server:
        # get template from server
        url = config.http_camera_server + config.http_path_get + '?' + \
            config.http_search_attr_name + '='  + config.templates[appLab]
        if config.debug:
            print ('DEBUG: url = ' + url)
        sxml = urllib2.urlopen(url).read()
        txml = ET.fromstring(sxml)
    else:
        # get template from local file
        if config.debug:
            print ('DEBUG: directory = ' + config.template_directory)
        lfile = os.path.join(config.template_directory, config.templates[appLab]['app'])
        if config.debug:
            print ('DEBUG: local file = ' + lfile)
        tree = ET.parse(lfile)
        txml = tree.getroot()

    # Find all CCD parameters
    cconfig = txml.find('configure_camera')
    pdict = {}
    for param in cconfig.findall('set_parameter'):
        pdict[param.attrib['ref']] = param.attrib

    # Set them. This is designed so that missing 
    # parameters will cause exceptions to be raised.

    # X-binning factor
    pdict['X_BIN']['value'] = ccdpars.xbin.get()

    # Y-binning factor
    pdict['X_BIN']['value'] = ccdpars.ybin.get()

    # Number of exposures
    pdict['NUM_EXPS']['value'] = '-1' if ccdpars.number.value() == 0 else ccdpars.number.get()

    # LED level
    pdict['LED_FLSH']['value'] = ccdpars.led.get()

    # Avalanche or normal
    pdict['OUTPUT']['value'] = str(ccdpars.avalanche())

    # Avalanche gain
    pdict['HV_GAIN']['value'] = ccdpars.avgain.get()

    # Clear or not
    pdict['EN_CLR']['value'] = str(ccdpars.clear())

    # Dwell
    pdict['DWELL']['value'] = ccdpars.expose.get()

    # Readout speed
    pdict['SPEED']['value'] = '0' if ccdpars.readout == 'Slow' else '1' \
        if ccdpars.readout == 'Medium' else '2'

    # Number of windows -- needed to set output parameters correctly
    nwin  = ccdpars.nwin.value()

    # Load up enabled windows, null disabled windows
    for nw, win in ccdpars.wframe.wins:
        if nw < nwin:
            pdict['X' + str(nw+1) + '_START']['value'] = win.xstart.get()
            pdict['Y' + str(nw+1) + '_START']['value'] = win.ystart.get()
            pdict['X' + str(nw+1) + '_SIZE']['value']  = win.nx.get()
            pdict['Y' + str(nw+1) + '_SIZE']['value']  = win.ny.get()
        else:
            pdict['X' + str(nw+1) + '_START']['value'] = '1'
            pdict['Y' + str(nw+1) + '_START']['value'] = '1'
            pdict['X' + str(nw+1) + '_SIZE']['value']  = '0'
            pdict['Y' + str(nw+1) + '_SIZE']['value']  = '0'

    # Load the user parameters
    uconfig = txml.find('user')
    uconfig.set('target', userpars.target.get())
    uconfig.set('comment', userpars.comment.get())
    uconfig.set('ID', userpars.progid.get())
    uconfig.set('PI', userpars.pi.get())
    uconfig.set('Observers', userpars.observers.get())
 
    return txml

class Actions(tk.LabelFrame):
    """
    Action buttons Frame. Collects together buttons that fire off external commands,
    such as loading data from disk, or sending data to servers. All of these need
    callback routines which are hidden within this class.
    """
        
    def __init__(self, master, config, ccdpars, userpars):
    
        tk.LabelFrame.__init__(self, master, text='Actions', padx=10, pady=10)

        width = 10
        self.load = tk.Button(self, text="Load", fg="black", width=width, \
                                  command=lambda : print('you have pressed the load button'))
        self.load.grid(row=0,column=0)

        self.save = tk.Button(self, text="Save", fg="black", width=width, \
                                  command=lambda : print('you have pressed the save button'))
        self.save.grid(row=1,column=0)

        self.post = Post(self, width, config, ccdpars, userpars)
        self.post.grid(row=0,column=1)

        self.start = Start(self, width, config, ccdpars)
        self.start.grid(row=1,column=1)

        self.stop = tk.Button(self, text="Stop", fg="black", bg=COL_STOP, width=width, \
                                  command=lambda : print('you have pressed the stop button'))
        self.stop.grid(row=2,column=1)
