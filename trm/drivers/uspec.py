#!/usr/bin/env python

"""
Python module supplying classes specific to ULTRASPEC
"""

from __future__ import print_function
import Tkinter as tk
import tkFont, tkMessageBox, tkFileDialog
import xml.etree.ElementTree as ET
import os
import drivers as drvs

# maximum number of windows on any application
MAXWIN = 4

class Window (object):
    """
    Class to define a plain Window with an x,y left-lower pixel
    and dimensions.
    """

    def __init__(self, master, row, column, xstart, ystart, nx, ny, xb, yb, checker):
        """
        Sets up a window pair as a row of values, initialised to
        the arguments supplied. The row is created within a sub-frame
        of master.

        Arguments:

          master :
            master widget within which the Frame containing the values
            will be placed. A grid layout will be adopted to allow
            other WindowPairs to abutted nicely, hence the row and
            column of the leftmost entry field must be specified

          row :
            row along which values will be placed

          column :
            first column for fields

          xstart :
            initial X value of the leftmost column of the window

          ystart :
            initial Y value of the lowest row of the window

          nx :
            X dimension of windows, unbinned pixels

          ny :
            Y dimension of windows, unbinned pixels

          xb : 
            xbinning factor; must have a 'get' method. Used to step nx.

          yb : 
            ybinning factor; must have a 'get' method. Used to step ny.

          checker : 
            checker function to provide a global check and update in response
            to any changes made to the values stored in a Window. Can be None. 
        """

        # A window needs 4 parameters to specify it:
        #
        #  xstart -- first x value to be read
        #  ystart -- first y value to be read
        #  nx     -- X dimension, unbinned pixels
        #  ny     -- Y dimension, unbinned pixels

        self.xstart = drvs.RangedPosInt(master, xstart, 1, 1056, checker, width=4)
        self.xstart.grid(row=row,column=column)

        self.ystart = drvs.RangedPosInt(master, ystart, 1, 1072, checker, width=4)
        self.ystart.grid(row=row,column=column+1)

        self.nx = drvs.RangedPosMInt(master, nx, 1, 1056, xb, checker, width=4)
        self.nx.grid(row=row,column=column+2)

        self.ny = drvs.RangedPosMInt(master, ny, 1, 1072, yb, checker, width=4)
        self.ny.grid(row=row,column=column+3)

    def get(self):
        "Returns current xstart, ystart, nx, ny values"
        return (self.xstart.get(),self.ystart.get(),self.nx.get(),self.ny.get())

    def check(self, xbin, ybin):
        """
        Checks the values of a Window. If any problems are found, it 
        flags them by changing the background colour.

        xbin -- X binning factor
        ybin -- Y binning factor

        Returns (status, synced)

          status : flag for whether parameters are viable at all
          synced : flag for whether the Window is synchronised.

        """

        # Get values
        xstart, ystart, nx, ny = self.get()

        # Are they all OK individually?
        status = self.xstart.ok() and self.ystart.ok() and self.nx.ok() and self.ny.ok()

        # Are unbinned dimensions consistent with binning factors?
        if nx is None or nx % xbin != 0:
            self.nx.config(bg=drvs.COL_ERROR)
            status = False

        if ny is None or ny % ybin != 0:
            self.ny.config(bg=drvs.COL_ERROR)
            status = False

        # Are the windows synchronised? This means that they would be consistent with
        # the pixels generated were the whole CCD to be binned by the same factors
        # If xstart or ystart are not set, we count that as "synced" because the purpose
        # of this is to enable / disable the sync button and we don't want it to be
        # enabled just because xstart or ystart are not set.
        synced = xstart is None or ystart is None or nx is None or ny is None or \
            ((xstart - 1) % xbin == 0 and (ystart - 1) % ybin == 0)
            
        # Now come cross-value checks:

        # Is rightmost pixel of lefthand window within range?
        if xstart is None or xstart + nx - 1 > 1056:
            self.xstart.config(bg=drvs.COL_ERROR)
            status = False

        # Is top pixel within range?
        if ystart is None or ystart + ny - 1 > 1072:
            self.ystart.config(bg=drvs.COL_ERROR)
            status = False

        if status:
            # set all OK if everything checks
            self.xstart.config(bg=drvs.COL_TEXT_BG)
            self.ystart.config(bg=drvs.COL_TEXT_BG)
            self.nx.config(bg=drvs.COL_TEXT_BG)
            self.ny.config(bg=drvs.COL_TEXT_BG)
            
        return (status, synced)
    
    def enable(self):
        self.xstart.enable()
        self.ystart.enable()
        self.nx.enable()
        self.ny.enable()

    def disable(self):
        self.xstart.disable()
        self.ystart.disable()
        self.nx.disable()
        self.ny.disable()

class UspecWins(tk.Frame):
    """
    Defines a block with window info
    """

    def __init__(self, master, confpars, xbin, ybin, checker):
        """
        master  : enclosing widget
        confpars : configuration parameters
        xbin    : xbinning factor (with a get method)
        ybin    : ybinning factor (with a get method)
        checker : callback that runs checks on the setup parameters. It is passed down 
                  to the individual Windows so that it is run any time a parameter is
                  changed.
        """          
        tk.Frame.__init__(self, master)

        # First row
        row    = 0
        column = 0

        # Spacer column between first and third
        column += 1
        tk.Label(self, text=' ').grid(row=0,column=column,padx=5)

        # Third column
        column += 1

        # First row: names of parameters
        small_font = tkFont.nametofont("TkDefaultFont").copy()
        small_font.configure(size=10)
        tk.Label(self, text='xstart', font=small_font).grid(row=row,column=column)
        tk.Label(self, text='ystart', font=small_font).grid(row=row,column=column+1)
        tk.Label(self, text='nx', font=small_font).grid(row=row,column=column+2)
        tk.Label(self, text='ny', font=small_font).grid(row=row,column=column+3)
        
        # Now window rows. Keep the labels as well so they can be disabled.
        self.wlabs = []
        self.wins  = []
        column = 0
        for i in range(MAXWIN):
            self.wlabs.append(tk.Label(self, text='Window ' + str(i+1)))
            self.wlabs[-1].grid(row=i+2,column=column, sticky=tk.W)
            self.wins.append(Window(self, i+2, column+2, 1+100*i, 1+100*i, 100, 100, xbin, ybin, checker))

        # Save confpars parameters
        self.confpars = confpars

    def check(self, nwin, xbin, ybin):
        """
        Checks the validity of the window parameters. 

          nwin : numbers of windows to check
          xbin : X-binning factor
          ybin : Y-binning factor

        Returns (status, synced), flags which indicate whether the window 
        parameters are viable and synced.
        """

        status = True
        synced = True
        
        # Pick up global status and need to synchronise
        for win in self.wins[:nwin]:
            stat, syncd = win.check(xbin, ybin)
            if not stat: status = False
            if not syncd: synced = False

        # Check that no two windows overlap
        for i,win1 in enumerate(self.wins[:nwin]):
            xl1,yl1,nx1,ny1 = win1.get()
            for j, win2 in enumerate(self.wins[i+1:nwin]):
                xl2,yl2,nx2,ny2 = win2.get()
                if drvs.overlap(xl1,yl1,nx1,ny1,xl2,yl2,nx2,ny2):
                    win2.xstart.config(bg=drvs.COL_ERROR)
                    win2.ystart.config(bg=drvs.COL_ERROR)
                    status = False
                    if self.config.debug:
                        print('DEBUG: windows',i+1,'and',i+j+2,'overlap.')

        return (status, synced)

class Sync(drvs.ActButton):
    """
    Class defining the 'Sync' button's operation. This moves the windows to ensure that
    the pixels are in step with a full-frame of the same binning.
    """

    def __init__(self, master, width, xbin, ybin, nwin, wframe, callback):
        """
        master   : containing widget
        width    : width of button
        xbin, ybin, nwin, wframe : window parameters
        """
        drvs.ActButton.__init__(self, master, width, {}, callback, text='Sync')        
        self.xbin   = xbin
        self.ybin   = ybin
        self.nwin   = nwin
        self.wframe = wframe

    def act(self):
        """
        Carries out the action associated with the Sync button
        """
        xbin = self.xbin.get()
        ybin = self.ybin.get()
        nwin = self.nwin.get()
        print('nwin=',nwin)
        for win in self.wframe.wins[:nwin]:
            print('here i am')
            xstart = win.xstart.get()
            xstart = xbin*((xstart-1)//xbin)+1
            win.xstart.set(xstart)
            ystart = win.ystart.get()
            ystart = ybin*((ystart-1)//xbin)+1
            win.ystart.set(ystart)
        self.config(bg=drvs.COL_MAIN)
        self.disable()
        self.callback()
    
class InstPars(tk.LabelFrame):
    """
    Ultraspec instrument parameters block.
    """
        
    def __init__(self, master, other):
        """
        master : enclosing widget

        other : dictionary of other objects needed by this widget
        """
        tk.LabelFrame.__init__(self, master, text='Instrument parameters', padx=10, pady=10)

        # First column: the labels
        row     = 0
        column  = 0
        tk.Label(self, text='Application').grid(row=row,column=column,sticky=tk.W)

        row += 1
        tk.Label(self, text='Clear').grid(row=row,column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='Avalanche').grid(row=row,column=column,sticky=tk.W)

        row += 1
        self.avgainLabel = tk.Label(self, text='Avalanche gain')
        self.avgainLabel.grid(row=row,column=column,sticky=tk.W)

        row += 1
        tk.Label(self, text='Readout speed').grid(row=row,column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='LED setting').grid(row=row,column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='Exposure delay').grid(row=row,column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='Num. exposures').grid(row=row,column=column, sticky=tk.W)

        # Spacer column between first and third columns
        column += 1
        tk.Label(self, text=' ').grid(row=0,column=column)

        # Second column: various entry fields
        row     = 0
        column += 1

        # Application
        self.appLab = drvs.Choice(self, ('Windows','Drift'), self.check)
        self.appLab.grid(row=row,column=column,sticky=tk.W)

        # Clear enabled
        row += 1
        self.clear = drvs.OnOff(self, True)
        self.clear.grid(row=row,column=column,sticky=tk.W)

        # Avalanche or not
        row += 1
        self.avalanche = drvs.OnOff(self, False, self.check)
        self.avalanche.grid(row=row,column=column,sticky=tk.W)

        # Avalanche gain
        row += 1
        self.avgain = drvs.RangedPosInt(self, 0, 0, 7, None, width=2)
        self.avgain.grid(row=row,column=column,sticky=tk.W)

        # Readout speed
        row += 1
        self.readout = drvs.Choice(self, ('Slow', 'Medium', 'Fast'))
        self.readout.grid(row=row,column=column,sticky=tk.W)

        # LED setting
        row += 1
        self.led = drvs.RangedPosInt(self, 0, 0, 4095, None, width=6)
        self.led.grid(row=row,column=column,sticky=tk.W)

        # Exposure delay
        row += 1
        self.expose = drvs.PosInt(self, 0, None, width=6)
        self.expose.grid(row=row,column=column,sticky=tk.W)

        # Number of exposures
        row += 1
        self.number = drvs.PosInt(self, 1, None, width=6)
        self.number.grid(row=row,column=column,sticky=tk.W)

        # Spacer column between third and fifth columns
        column += 1
        tk.Label(self, text='   ').grid(row=0,column=column)

        # Fifth column
        column += 1
        colstart = column

        # First row: binning factors
        row = 0
        tk.Label(self, text='Binning factors (X x Y)').grid(row=row,column=column, sticky=tk.W)

        # Spacer
        column += 1
        tk.Label(self, text=' ').grid(row=row,column=column)

        column += 1
        xyframe = tk.Frame(self)
        self.xbin = drvs.RangedPosInt(xyframe, 1, 1, 8, self.check, width=2)
        self.xbin.pack(side=tk.LEFT)

        tk.Label(xyframe, text=' x ').pack(side=tk.LEFT)

        self.ybin = drvs.RangedPosInt(xyframe, 1, 1, 8, self.check, width=2)
        self.ybin.pack(side=tk.LEFT)

        xyframe.grid(row=row,column=column,columnspan=4,sticky=tk.W)

        # Second row: number of windows
        row += 1
        column = colstart
        tk.Label(self, text='Number of windows').grid(row=row,column=column, sticky=tk.W)

        column += 2
        self.nwin = drvs.RangedPosInt(self, 1, 1, MAXWIN, self.check, width=2)
        self.nwin.grid(row=row,column=column,sticky=tk.W,columnspan=4,pady=10)
        
        # Third row: the windows
        row += 1
        self.wframe = UspecWins(self, other['confpars'], self.xbin, self.ybin, self.check)
        self.wframe.grid(row=row,column=colstart,rowspan=6,columnspan=3,sticky=tk.W+tk.N)

        # Final row: buttons to synchronise windows.
        row += 1
        self.sync = Sync(self, 5, self.xbin, self.ybin, self.nwin, self.wframe, self.check)
        self.sync.grid(row=7,column=colstart,sticky=tk.W)

        # Store configuration parameters
        self.other = other

        # flag showing freeze state
        self.frozen = False

        # Run an initial check
        self.check()

    def check(self, *args):
        """
        Callback function for running validity checks on the CCD
        parameters. It spots and flags overlapping windows, windows with null
        parameters, windows with invalid dimensions given the binning
        factors. It sets the correct number of windows according to the
        selected application and enables or disables the avalanche gain
        setting according to whether the avalanche output is being used.
        Finally it checks that the windows are synchronised and sets the
        status of the 'Sync' button accordingly.

        Returns True/False according to whether the settings are judged to be 
        OK. True means they are thought to be in a fit state to be sent to the
        camera.
        """
        confpars = self.other['confpars']

        if confpars['debug']:
            print('Running uspec.InstPars.check')

        # Adjust number of windows according to the application
        if self.appLab.val.get() == 'Windows':
            self.nwin.imax == MAXWIN
            if not self.frozen: self.nwin.enable()
        elif self.appLab.val.get() == 'Drift':
            self.nwin.imax == 1
            self.nwin.val.set(1)
            self.nwin.disable()

        # enable / disable windows
        nwin = self.nwin.get()
        for win in self.wframe.wins[nwin:]:
            win.disable()
        for wlab in self.wframe.wlabs[nwin:]:
            wlab.configure(state='disable')

        if not self.frozen: 
            for win in self.wframe.wins[:nwin]:
                win.enable()
        for wlab in self.wframe.wlabs[:nwin]:
            wlab.configure(state='normal')

        # check avalanche settings
        if self.avalanche():
            if not self.frozen: self.avgain.enable()
            self.avgainLabel.configure(state='normal')
            self.avgain.val.set(0)
        else:
            self.avgain.disable()
            self.avgainLabel.configure(state='disable')
 
       # finally check the window settings
        status, synced = self.wframe.check(self.nwin.get(),self.xbin.get(),self.ybin.get())
        if confpars['debug']:
            print('status =',status,'synced =',synced)

        if status and not synced:
            if not self.frozen: 
                self.sync.configure(state='normal')
            self.sync.config(bg=drvs.COL_WARN)
        else:
            self.sync.config(bg=drvs.COL_MAIN)
            self.sync.configure(state='disable')

        observe = self.other['observe']
        if observe:
            # If the observe widget is set, then we can enable or
            # disable the 'Post' buttong according to the results of 
            # the check.
            if status:
                observe.post.enable()
            else:
                observe.post.disable()

        return status

    def freeze(self):
        """
        Freeze all settings so that they can't be altered
        """
        self.appLab.disable()
        self.clear.disable()
        self.avalanche.disable()
        self.avgain.disable()
        self.readout.disable()
        self.led.disable()
        self.expose.disable()
        self.number.disable()
        self.xbin.disable()
        self.ybin.disable()
        self.nwin.disable()
        for win in self.wframe.wins:
            win.disable()
        self.sync.configure(state='disable')
        self.frozen = True

    def melt(self):
        """
        Reverse of freeze
        """
        self.appLab.enable()
        self.clear.enable()
        self.avalanche.enable()
        self.readout.enable()
        self.led.enable()
        self.expose.enable()
        self.number.enable()
        self.xbin.enable()
        self.ybin.enable()
        self.nwin.enable()
        self.frozen = False
        self.check()

    def getRtplotWins(self):
        """
        Returns a string suitable to sending off to rtplot when
        it asks for window parameters. Returns null string '' if
        the windows are not OK. This operates on the basis of
        trying to send something back, even if it might not be 
        OK as a window setup. Note that we have to take care
        here not to update any GUI components because this is 
        called outside of the main thread.
        """
        try:
            xbin = self.xbin.val.get()
            ybin = self.ybin.val.get()
            nwin = self.nwin.val.get()
            ret  = str(xbin) + ' ' + str(ybin) + ' ' + str(nwin) + '\r\n'
            for win in self.wframe.wins[:nwin]:
                xstart = win.xstart.val.get()
                ystart = win.xstart.val.get()
                nx     = win.nx.val.get()
                ny     = win.ny.val.get()
                ret   += str(xstart) + ' ' + str(ystart) + ' ' + str(nx) + ' ' + str(ny) + '\r\n'
            return ret
        except:
            return ''

class RunPars(tk.LabelFrame):
    """
    Run parameters
    """
        
    def __init__(self, master):
        tk.LabelFrame.__init__(self, master, text='Run parameters', padx=10, pady=10)

        row     = 0
        column  = 0
        tk.Label(self, text='Target name').grid(row=row,column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='Programme ID').grid(row=row,column=column, sticky=tk.W)
            
        row += 1
        tk.Label(self, text='Principal Investigator').grid(row=row,column=column, sticky=tk.W)
            
        row += 1
        tk.Label(self, text='Observer(s)').grid(row=row,column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='Pre-run comment').grid(row=row,column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='Data type').grid(row=row,column=column, sticky=tk.W+tk.N)

            
        # spacer
        column += 1
        tk.Label(self, text=' ').grid(row=0,column=column)

        # target
        row     = 0
        column += 1
        self.target = drvs.TextEntry(self, width=30)
        self.target.grid(row=row, column=column, sticky=tk.W)

        # programme ID
        row += 1
        self.progid = drvs.TextEntry(self, width=20)
        self.progid.grid(row=row, column=column, sticky=tk.W)

        # principal investigator
        row += 1
        self.pi = drvs.TextEntry(self, width=20)
        self.pi.grid(row=row, column=column, sticky=tk.W)

        # observers
        row += 1
        self.observers = drvs.TextEntry(self, width=20)
        self.observers.grid(row=row, column=column, sticky=tk.W)

        # comment
        row += 1
        self.comment = drvs.TextEntry(self, width=38)
        self.comment.grid(row=row, column=column, sticky=tk.W)

        # data types
        row += 1
        DTYPES = ('acquisition','science','bias','flat','dark','technical')
    
        self.dtype = tk.StringVar()
        self.dtype.set('undef') 
    
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

# Observing section. First a helper routine needed
# by the 'Save' and 'Post' buttons

def createXML(confpars, instpars, runpars):
    """
    This creates the XML representing the current setup. It does
    this by loading a template xml file using directives in the
    configuration parameters, and then imposing the current settings

    Arguments:

      confpars   : configuration parameters
      instpars  : windows etc
      runpars : target, PI nam,e etc.

    Returns a xml.etree.ElementTree.Element
    """

    # identify the template
    appLab = instpars.appLab.get()
    if confpars['debug']:
        print('DEBUG: createXML: application = ' + appLab)
        print('DEBUG: createXML: application vals = ' + str(confpars['templates'][appLab]))

    if confpars['template_from_server']:
        # get template from server
        url = confpars['http_camera_server'] + confpars['http_path_get'] + '?' + \
            confpars['http_search_attr_name'] + '='  + confpars['templates'][appLab]
        if confpars['debug']:
            print ('DEBUG: url = ' + url)
        sxml = urllib2.urlopen(url).read()
        root = ET.fromstring(sxml)
    else:
        # get template from local file
        if confpars['debug']:
            print ('DEBUG: directory = ' + confpars['template_directory'])
        lfile = os.path.join(confpars['template_directory'], confpars['templates'][appLab]['app'])
        if confpars['debug']:
            print ('DEBUG: local file = ' + lfile)
        tree = ET.parse(lfile)
        root = tree.getroot()

    # Find all CCD parameters
    cconfig = root.find('configure_camera')
    pdict = {}
    for param in cconfig.findall('set_parameter'):
        pdict[param.attrib['ref']] = param.attrib

    # Set them. This is designed so that missing 
    # parameters will cause exceptions to be raised.

    # X-binning factor
    pdict['X_BIN']['value'] = str(instpars.xbin.get())

    # Y-binning factor
    pdict['Y_BIN']['value'] = str(instpars.ybin.get())

    # Number of exposures
    pdict['NUM_EXPS']['value'] = '-1' if instpars.number.get() == 0 \
        else str(instpars.number.get())

    # LED level
    pdict['LED_FLSH']['value'] = str(instpars.led.get())

    # Avalanche or normal
    pdict['OUTPUT']['value'] = str(instpars.avalanche())

    # Avalanche gain
    pdict['HV_GAIN']['value'] = str(instpars.avgain.get())

    # Clear or not
    pdict['EN_CLR']['value'] = str(instpars.clear())

    # Dwell
    pdict['DWELL']['value'] = str(instpars.expose.get())

    # Readout speed
    pdict['SPEED']['value'] = '0' if instpars.readout == 'Slow' else '1' \
        if instpars.readout == 'Medium' else '2'

    # Number of windows -- needed to set output parameters correctly
    nwin  = int(instpars.nwin.get())

    # Load up enabled windows, null disabled windows
    for nw, win in enumerate(instpars.wframe.wins):
        if nw < nwin:
            pdict['X' + str(nw+1) + '_START']['value'] = str(win.xstart.get())
            pdict['Y' + str(nw+1) + '_START']['value'] = str(win.ystart.get())
            pdict['X' + str(nw+1) + '_SIZE']['value']  = str(win.nx.get())
            pdict['Y' + str(nw+1) + '_SIZE']['value']  = str(win.ny.get())
        else:
            pdict['X' + str(nw+1) + '_START']['value'] = '1'
            pdict['Y' + str(nw+1) + '_START']['value'] = '1'
            pdict['X' + str(nw+1) + '_SIZE']['value']  = '0'
            pdict['Y' + str(nw+1) + '_SIZE']['value']  = '0'

    # Load the user parameters
    uconfig = root.find('user')

    uconfig.set('target', runpars.target.get())
    uconfig.set('comment', runpars.comment.get())
    uconfig.set('dtype', runpars.dtype.get())
    uconfig.set('ID', runpars.progid.get())
    uconfig.set('PI', runpars.pi.get())
    uconfig.set('Observers', runpars.observers.get())
 
    return root

class Post(drvs.ActButton):
    """
    Class defining the 'Post' button's operation
    """

    def __init__(self, master, width, other):
        """
        master   : containing widget
        width    : width of button
        other    : other objects 'confpars', 'instpars', 'runpars', 'commLog', 'respLog'
        """        
        drvs.ActButton.__init__(self, master, width, other, text='Post')

    def act(self):
        """
        Carries out the action associated with Post button
        """

        o = self.other
        cpars, ipars, rpars, clog, rlog = \
            o['confpars'], o['instpars'], o['runpars'], o['commLog'], o['respLog']
        
        if not ipars.check():
            # I hope the next message is never shown, but I leave it here for safety
            tkMessageBox.showwarning('Post failure','The current settings are invalid;\nplease fix them before posting.')
            return False

        # Get XML from template
        root = createXML(cpars, ipars, rpars)

        # Post to server
        drvs.postXML(root, cpars, clog, rlog)

        # Update other buttons ?? need a test of whether
        # a run is in progress
        o['Start'].enable()

        return True

class Load(drvs.ActButton):
    """
    Class defining the 'Load' button's operation. This loads a previously
    saved configuration from disk.
    """

    def __init__(self, master, width, other):
        """
        master  : containing widget
        width   : width of button
        other   : dictionary of other objects. Must have 'instpars' the instrument
                  setup parameters (windows etc), and 'runpars' the run parameters 
                  (target name etc)
        """
        drvs.ActButton.__init__(self, master, width, other, text='Load')

    def act(self):
        """
        Carries out the action associated with the Load button
        """

        fname = tkFileDialog.askopenfilename(defaultextension='.xml', filetypes=[('xml files', '.xml'),])
        if not fname: 
            other['commLog'].warn('Aborted load from disk')
            return False

        # load XML
        tree = ET.parse(fname)
        root = tree.getroot()

        # find parameters
        cconfig = root.find('configure_camera')
        pdict = {}
        for param in cconfig.findall('set_parameter'):
            pdict[param.attrib['ref']] = param.attrib['value']

        # Set them. 
        instpars = self.other['instpars']

        # X-binning factor
        instpars.xbin.set(pdict['X_BIN'])

        # Y-binning factor
        instpars.ybin.set(pdict['Y_BIN'])

        # Number of exposures
        instpars.number.set(pdict['NUM_EXPS'] if pdict['NUM_EXPS'] != '-1' else 0)

        # LED level
        instpars.led.set(pdict['LED_FLSH'])

        # Avalanche or normal
        instpars.avalanche.set(pdict['OUTPUT'])

        # Avalanche gain
        instpars.avgain.set(pdict['HV_GAIN'])

        # Clear or not
        instpars.clear.set(pdict['EN_CLR'])

        # Dwell
        instpars.expose.set(pdict['DWELL'])

        # Readout speed
        speed = pdict['SPEED']
        instpars.readout.set('Slow' if speed == '0' else 'Medium' if speed == '1' \
                                 else 'Fast') 

        # Load up windows
        nwin = 0
        start = True
        for nw, win in instpars.wframe.wins:
            xs = 'X' + str(nw+1) + '_START'
            ys = 'X' + str(nw+1) + '_START'
            nx = 'X' + str(nw+1) + '_SIZE'
            ny = 'Y' + str(nw+1) + '_SIZE'
            if start and xs in pdict and ys in pdict and nx in pdict and ny in pdict \
                    and pdict[nx] != '0' and pdict[ny] != 0:
                win.enable()
                win.xstart.set(pdict[xs])
                win.ystart.set(pdict[ys])
                win.nx.set(pdict[nx])
                win.ny.set(pdict[ny])
                nwin += 1
            else:
                start = False
                win.disable()

        # Set the number of windows
        nwin  = instpars.nwin.get()

        # User parameters ...

        return True

class Save(drvs.ActButton):
    """
    Class defining the 'Save' button's operation. This saves the
    current configuration to disk.
    """

    def __init__(self, master, width, other):
        """
        master  : containing widget
        width   : width of button
        other   : dictionary of other objects. Must have 'confpars' the configuration
                  parameters, 'instpars' the instrument setup parameters (windows etc), 
                  and 'runpars' the run parameters (target name etc), 'commLog'
        """
        drvs.ActButton.__init__(self, master, width, other, text='Save')        

    def act(self):
        """
        Carries out the action associated with the Save button
        """

        o = self.other
        cpars, ipars, rpars, clog, rlog = \
            o['confpars'], o['instpars'], o['runpars'], o['commLog'], o['respLog']

        # Get XML from template
        root = createXML(cpars, ipars, rpars)

        # Save to disk
        drvs.saveXML(root, clog)

        ipars.melt()
        return True

class Unfreeze(drvs.ActButton):
    """
    Class defining the 'Unfreeze' button's operation. 
    """

    def __init__(self, master, width, other):
        """
        master  : containing widget
        width   : width of button
        other   : dictionary of other objects needed. Needs 'instpars', the current instrument 
                  parameters to be loaded up once the template is loaded
        """
        drvs.ActButton.__init__(self, master, width, other, text='Unfreeze')

    def act(self):
        """
        Carries out the action associated with the Unfreeze button
        """
        self.other['instpars'].melt()
        self.disable()

class Observe(tk.LabelFrame):
    """
    Observe Frame. Collects together buttons that fire off the commands needed
    during observing. These have in common interaction with external objects,
    such as loading data from disk, or sending data to servers. All of these need
    callback routines which are hidden within this class.
    """
    
    def __init__(self, master, other):
    
        tk.LabelFrame.__init__(self, master, text='Observing commands', padx=10, pady=10)

        # create buttons
        width = 10
        self.load = Load(self, width, other)
        self.save = Save(self, width, other)
        self.unfreeze = Unfreeze(self, width, other)
        self.post = Post(self, width, other)
        self.start = drvs.Start(self, width, other)
        self.stop = drvs.Stop(self, width, other)

        # pass all buttons to each other
        other['Load']     = self.load
        other['Save']     = self.save
        other['Unfreeze'] = self.unfreeze
        other['Post']     = self.post
        other['Start']    = self.start
        other['Stop']     = self.stop

        self.other = other

        # Lay them out
        self.load.grid(row=0,column=0)
        self.save.grid(row=1,column=0)
        self.unfreeze.grid(row=2,column=0)
        self.post.grid(row=0,column=1)
        self.start.grid(row=1,column=1)
        self.stop.grid(row=2,column=1)

        # Define initial status
        self.post.disable()
        self.start.disable()
        self.stop.disable()

        # implement expert level
        self.setExpertLevel(other['confpars']['expert_level'])

    def setExpertLevel(self, level):
        """
        Set expert level
        """

        # now set whether buttons are permanently enabled or not
        if level == 0 or level == 1:
            self.load.setNonExpert()
            self.save.setNonExpert()
            self.unfreeze.setNonExpert()
            self.post.setNonExpert()
            self.start.setNonExpert()
            self.stop.setNonExpert()

        elif level == 2:
            self.load.setExpert()
            self.save.setExpert()
            self.unfreeze.setExpert()
            self.post.setExpert()
            self.start.setExpert()
            self.stop.setExpert()
