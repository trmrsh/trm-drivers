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
import math as m

# maximum number of windows on any application
MAXWIN = 4

# Timing, gain, noise parameters lifted from java usdriver
VCLOCK           =  14.4e-6  # vertical clocking time 
HCLOCK_NORM      =  0.48e-6  # normal mode horizontal clock
HCLOCK_AV        =  0.96e-6  # avalanche mode horizontal clock
VIDEO_NORM_SLOW  = 11.20e-6  
VIDEO_NORM_MED   =  6.24e-6
VIDEO_NORM_FAST  =  3.20e-6
VIDEO_AV_SLOW    = 11.20e-6
VIDEO_AV_MED     =  6.24e-6
VIDEO_AV_FAST    =  3.20e-6
FFX              = 1072
FFY              = 1072
IFY              = 1072
IFX              = 1072
AVALANCHE_PIXELS = 1072

AVALANCHE_GAIN_9   = 1200.0  # dimensionless gain, hvgain=9
AVALANCHE_SATURATE = 80000   # electrons

# avalanche gains assume HVGain = 9. We can adapt this later when we decide how
# gain should be set at TNO. Might be better to make gain a function if we allow 
# 0 < HVgain < 9 (SL)

GAIN_NORM_FAST = 0.8    # electrons per count
GAIN_NORM_MED  = 0.7    # electrons per count
GAIN_NORM_SLOW = 0.8    # electrons per count
GAIN_AV_FAST   = 0.0034 # electrons per count
GAIN_AV_MED    = 0.0013 # electrons per count
GAIN_AV_SLOW   = 0.0016 # electrons per count

# Note - avalanche RNO assume HVGain = 9. We can adapt this later when we decide how
# gain should be set at TNO. Might be better to make RNO a function if we allow 0 < HVgain < 9 (SL)
   
RNO_NORM_FAST  =  4.8 # electrons per pixel
RNO_NORM_MED   =  2.8 # electrons per pixel
RNO_NORM_SLOW  =  2.2 # electrons per pixel
RNO_AV_FAST    = 16.5 # electrons per pixel
RNO_AV_MED     =  7.8 # electrons per pixel
RNO_AV_SLOW    =  5.6 # electrons per pixel

# other noise sources
DARK_E         =  0.001 # electrons/pix/sec
CIC            =  0.010 # Clock induced charge, electrons/pix


class Window (object):
    """
    Class to define a plain Window with an x,y left-lower pixel
    and dimensions.
    """

    def __init__(self, master, row, column, xstart, ystart, nx, ny, xbin, ybin, checker):
        """
        Sets up a window pair as a row of values, initialised to
        the arguments supplied. The row is created within a sub-frame
        of master.

        Arguments:

          master :
            master widget within which the Frame containing the values
            will be placed. A grid layout will be adopted to allow
            other Windows to abutted nicely, hence the row and
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

          xbin : 
            xbinning factor; must have a 'value' method. Used to step and check nx

          ybin : 
            ybinning factor; must have a 'value' method. Used to step and check ny 

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

        self.xstart = drvs.RangedInt(master, xstart, 1, 1056, checker, True, width=4)
        self.xstart.grid(row=row,column=column)

        self.ystart = drvs.RangedInt(master, ystart, 1, 1072, checker, True, width=4)
        self.ystart.grid(row=row,column=column+1)

        self.nx = drvs.RangedMint(master, nx, 1, 1056, xbin, checker, True, width=4)
        self.nx.grid(row=row,column=column+2)

        self.ny = drvs.RangedMint(master, ny, 1, 1072, ybin, checker, True, width=4)
        self.ny.grid(row=row,column=column+3)

        self.xbin = xbin
        self.ybin = ybin
        

    def value(self):
        "Returns current xstart, ystart, nx, ny values"
        return (self.xstart.value(),self.ystart.value(),self.nx.value(),self.ny.value())

    def check(self):
        """
        Checks the values of a Window. If any problems are found, it 
        flags them by changing the background colour.

        Returns (status, synced)

          status : flag for whether parameters are viable at all
          synced : flag for whether the Window is synchronised.

        """

        # set all OK to start with
        self.xstart.config(bg=drvs.COL['text_bg'])
        self.ystart.config(bg=drvs.COL['text_bg'])
        self.nx.config(bg=drvs.COL['text_bg'])
        self.ny.config(bg=drvs.COL['text_bg'])    

        # Get values
        xstart, ystart, nx, ny = self.value()
        xbin = self.xbin.value()
        ybin = self.ybin.value()

        # Are they all OK individually?
        status = self.xstart.ok() and self.ystart.ok() and self.nx.ok() and self.ny.ok()

        # Are unbinned dimensions consistent with binning factors?
        if nx is None or nx % xbin != 0:
            self.nx.config(bg=drvs.COL['error'])
            status = False

        if ny is None or ny % ybin != 0:
            self.ny.config(bg=drvs.COL['error'])
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
            self.xstart.config(bg=drvs.COL['error'])
            status = False

        # Is top pixel within range?
        if ystart is None or ystart + ny - 1 > 1072:
            self.ystart.config(bg=drvs.COL['error'])
            status = False

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

    def __init__(self, master, cpars, xbin, ybin, checker):
        """
        master  : enclosing widget
        cpars : configuration parameters
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

        # Save cpars parameters
        self.cpars = cpars

    def check(self, nwin):
        """
        Checks the validity of the window parameters. 

          nwin : numbers of windows to check

        Returns (status, synced), flags which indicate whether the window 
        parameters are viable and synced.
        """

        status = True
        synced = True
        
        # Pick up global status and need to synchronise
        for win in self.wins[:nwin]:
            stat, syncd = win.check()
            if not stat: status = False
            if not syncd: synced = False

        # Check that no two windows overlap
        for i,win1 in enumerate(self.wins[:nwin]):
            xl1,yl1,nx1,ny1 = win1.value()
            for j, win2 in enumerate(self.wins[i+1:nwin]):
                xl2,yl2,nx2,ny2 = win2.value()
                if drvs.overlap(xl1,yl1,nx1,ny1,xl2,yl2,nx2,ny2):
                    win2.xstart.config(bg=drvs.COL['error'])
                    win2.ystart.config(bg=drvs.COL['error'])
                    status = False

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
        xbin = self.xbin.value()
        ybin = self.ybin.value()
        nwin = self.nwin.value()
        for win in self.wframe.wins[:nwin]:
            xstart = win.xstart.value()
            xstart = xbin*((xstart-1)//xbin)+1
            win.xstart.set(xstart)
            ystart = win.ystart.value()
            ystart = ybin*((ystart-1)//xbin)+1
            win.ystart.set(ystart)
        self.config(bg=drvs.COL['main'])
        self.disable()
        self.callback()
    
class InstPars(tk.LabelFrame):
    """
    Ultraspec instrument parameters block.
    """
        
    def __init__(self, master, share):
        """
        master : enclosing widget
        share  : dictionary of other objects needed by this widget. 
                 These are 'observe' and 'cpars'
        """
        tk.LabelFrame.__init__(self, master, text='Instrument parameters', 
                               padx=10, pady=10)

        # First column: the labels
        row     = 0
        column  = 0
        tk.Label(self, text='Mode').grid(row=row,column=column,sticky=tk.W)

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
        self.appLab = drvs.Radio(self, ('Wins', 'Drift'), 2, self.check, ('Windows', 'Drift'))
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
        self.avgain = drvs.RangedInt(self, 0, 0, 7, None, False, width=2)
        self.avgain.grid(row=row,column=column,sticky=tk.W)

        # Readout speed
        row += 1
        self.readSpeed = drvs.Radio(self, ('S', 'M', 'F'), 3, self.check, ('Slow', 'Medium', 'Fast'))
        self.readSpeed.grid(row=row,column=column,sticky=tk.W)

        # LED setting
        row += 1
        self.led = drvs.RangedInt(self, 0, 0, 4095, None, False, width=6)
        self.led.grid(row=row,column=column,sticky=tk.W)

        # Exposure delay
        row += 1
        self.expose = drvs.PosInt(self, 0, None, False, width=6)
        self.expose.grid(row=row,column=column,sticky=tk.W)

        # Number of exposures
        row += 1
        self.number = drvs.PosInt(self, 1, None, False, width=6)
        self.number.grid(row=row,column=column,sticky=tk.W)

        # Spacer column between third and fifth columns
        column += 1
        tk.Label(self, text='   ').grid(row=0,column=column)

        # Fifth column
        column += 1
        colstart = column

        # First row: binning factors
        row = 0
        tk.Label(self, text='Binning factors (X x Y)').grid(row=row,
                                                            column=column, sticky=tk.W)
        # Spacer
        column += 1
        tk.Label(self, text=' ').grid(row=row,column=column)

        column += 1
        xyframe = tk.Frame(self)
        self.xbin = drvs.RangedInt(xyframe, 1, 1, 8, self.check, False, width=2)
        self.xbin.pack(side=tk.LEFT)

        tk.Label(xyframe, text=' x ').pack(side=tk.LEFT)

        self.ybin = drvs.RangedInt(xyframe, 1, 1, 8, self.check, False, width=2)
        self.ybin.pack(side=tk.LEFT)

        xyframe.grid(row=row,column=column,columnspan=4,sticky=tk.W)

        # Second row: number of windows
        row += 1
        column = colstart
        tk.Label(self, text='Number of windows').grid(row=row,column=column, sticky=tk.W)

        column += 2
        self.nwin = drvs.RangedInt(self, 1, 1, MAXWIN, self.check, False, width=2)
        self.nwin.grid(row=row,column=column,sticky=tk.W,columnspan=4,pady=10)
        
        # Third row: the windows
        row += 1
        self.wframe = UspecWins(self, share['cpars'], self.xbin, self.ybin, self.check)
        self.wframe.grid(row=row,column=colstart,rowspan=6,columnspan=3,sticky=tk.W+tk.N)

        # Final row: buttons to synchronise windows.
        row += 1
        self.sync = Sync(self, 5, self.xbin, self.ybin, self.nwin, self.wframe, self.check)
        self.sync.grid(row=7,column=colstart,sticky=tk.W)

        # Store configuration parameters and freeze state
        self.share  = share
        self.frozen = False

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

        This can only be run once the 'observe' and 'cpars' are defined.
        """
        o = self.share
        cpars, observe, cframe = o['cpars'], o['observe'], o['cframe']

        # Adjust number of windows according to the application
        if self.appLab.value() == 'Windows':
            self.nwin.imax == MAXWIN
            if not self.frozen: self.nwin.enable()
        elif self.appLab.value() == 'Drift':
            self.nwin.imax == 1
            self.nwin.set(1)
            self.nwin.disable()

        # enable / disable windows
        nwin = self.nwin.value()
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
            self.avgain.set(0)
        else:
            self.avgain.disable()
            self.avgainLabel.configure(state='disable')
 
        # finally check the window settings
        status, synced = self.wframe.check(self.nwin.value())

        if status and not synced:
            if not self.frozen: 
                self.sync.configure(state='normal')
            self.sync.config(bg=drvs.COL['warn'])
        else:
            self.sync.config(bg=drvs.COL['main'])
            self.sync.configure(state='disable')

        # allow posting according to whether the parameters are ok
        # update count and S/N estimates as well
        if status:
            observe.post.enable()
            cframe.update()
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
        self.readSpeed.disable()
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

    def unfreeze(self):
        """
        Reverse of freeze
        """
        self.appLab.enable()
        self.clear.enable()
        self.avalanche.enable()
        self.readSpeed.enable()
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
            xbin = self.xbin.value()
            ybin = self.ybin.value()
            nwin = self.nwin.value()
            ret  = str(xbin) + ' ' + str(ybin) + ' ' + str(nwin) + '\r\n'
            for win in self.wframe.wins[:nwin]:
                xstart = win.xstart.value()
                ystart = win.xstart.value()
                nx     = win.nx.value()
                ny     = win.ny.value()
                ret   += str(xstart) + ' ' + str(ystart) + ' ' + \
                    str(nx) + ' ' + str(ny) + '\r\n'
            return ret
        except:
            return ''

    def timing(self):
        """
        Estimates timing information for the current setup. You should
        run a check on the instrument parameters before calling this.

        Returns: (expTime, deadTime, cycleTime, dutyCycle) 

        expTime   : exposure time per frame (seconds)
        deadTime  : dead time per frame (seconds)
        cycleTime : sampling time (cadence), (seconds)
        dutyCycle : percentage time exposing.
        frameRate : number of frames per second
        """

        # avalanche mode y/n?
        lnormal = not self.avalanche()
        HCLOCK  = HCLOCK_NORM if lnormal else HCLOCK_AV;
		
        # drift mode y/n?
        isDriftMode = self.appLab.value() == 'Drift'

        # Set the readout speed
        readSpeed = self.readSpeed.value()

        if readSpeed == 'Fast':
            video = VIDEO_NORM_FAST if lnormal else VIDEO_AV_FAST
        elif readSpeed == 'Medium':
            video = VIDEO_NORM_MED if lnormal else VIDEO_AV_MED
        elif readSpeed == 'Slow':
            video = VIDEO_NORM_SLOW if lnormal else VIDEO_AV_SLOW
        else:
            raise drvs.DriverError('uspec.InstPars.timing: readout speed = ' \
                                       + readSpeed + ' not recognised.')

        # clear chip on/off?
        lclear = isDriftMode and self.clear 

        # get exposure delay (in units of 0.1 ms ?? check) and binning factors
        expose = self.expose.value()
        xbin   = self.xbin.value()	
        ybin   = self.ybin.value()	

        # window parameters
        xstart, ystart, nx, ny = [], [], [], []
        nwin = self.nwin.value()
        for win in self.wframe.wins[:nwin]:
            xstart.append(win.xstart.value())
            ystart.append(win.ystart.value())
            nx.append(win.nx.value())
            ny.append(win.ny.value())
            
        # alternatives for drift mode
        dxleft  = win.xstart.value()
        dxright = win.xstart.value()
        dystart = win.ystart.value()
        dnx     = win.nx.value()
        dny     = win.ny.value()

        if lnormal:
            # normal mode convert xstart by ignoring 16 overscan pixels
            for nw in xrange(nwin):
                xstart[nw] += 16
            dxleft  += 16
            dxright += 16
        else:
            # in avalanche mode, need to swap windows around
            for nw in xrange(nwin):
                xstart[nw] = FFX - (xstart[nw]-1) - (nx[nw]-1)

            dxright = FFX - (dxright-1) - (dnx-1)
            dxleft  = FFX - (dxleft-1) - (dnx-1)

            # in drift mode, also need to swap the windows around
            dxright, dxleft = dxleft, dxright
		    
        # convert timing parameters to seconds
        expose_delay = 1.0e-4*expose

        # clear chip by VCLOCK-ing the image and storage areas
        if lclear:
            # accomodate changes to clearing made by DA to fix dark current
            # when clearing charge along normal output
            clear_time = 2.0*(FFY*VCLOCK+39.e-6) + FFX*HCLOCK_NORM + \
                2162.0*HCLOCK_AV
        else:
            clear_time = 0.0

        # for drift mode, we need the number of windows in the pipeline and 
        # the pipeshift
        pnwin  = int(((1037. / dny) + 1.)/2.)
        pshift = 1037.- (2.*pnwin-1.)*dny

        # If not drift mode, move entire image into storage area
        # the -35 component is because Derek only shifts 1037 pixels
        # (composed of 1024 active rows, 5 dark reference rows, 2 
        # transition rows and 6 extra overscan rows for good measure) 
        # If drift mode, just move the window into the storage area
        
        frame_transfer = (FFY-35)*VCLOCK + 49.0e-6
        if isDriftMode:
            frame_transfer = (dny+dystart-1.)*VCLOCK + 49.0e-6

        # calculate the yshift, which places windows adjacent to the 
        # serial register
        yshift = nwin*[0.]
        if isDriftMode: 
            yshift[0]=(dystart-1.0)*VCLOCK
        else:
            yshift[0]=(ystart[0]-1.0)*VCLOCK
            for nw in xrange(1,nwin):
                yshift[nw] = (ystart[nw]-ystart[nw-1]-ny[nw-1])*VCLOCK
		
        # After placing the window adjacent to the serial register, the 
        # register must be cleared by clocking out the entire register, 
        # taking FFX hclocks (we no longer open the dump gates, which 
        # took only 8 hclock cycles to complete, but gave ramps and 
        # bright rows in the bias). We think dave does 2*FFX hclocks 
        # in avalanche mode, but need to check this with him.

        line_clear = nwin*[0.]
        hclockFactor = 1.0 if lnormal else 2.0
        if isDriftMode:
            if yshift[0] != 0: 
                line_clear[0] = hclockFactor*FFX*HCLOCK
            else:
                for nw in xrange(nwin):
                    if yshift[nw] != 0: 
                        line_clear[nw] = hclockFactor*FFX*HCLOCK

        # calculate how long it takes to shift one row into the serial register
        # shift along serial register and then read out the data. The charge 
        # in a row after a window used to be dumped, taking 8 HCLOCK cycles. 
        # This created ramps and bright rows/columns in the images, so was 
        # removed.
        numhclocks = nwin*[0]
        if isDriftMode:
            numhclocks[0] = FFX
            if not lnormal: 
                numhclocks[0] += AVALANCHE_PIXELS
        else:
            for nw in xrange(nwin):
                numhclocks[nw] = FFX;
                if not lnormal:
                    numhclocks[nw] += AVALANCHE_PIXELS

        line_read = nwin*[0.]
        if isDriftMode:
            line_read[0] = VCLOCK*ybin + numhclocks[0]*HCLOCK + \
                video*2.0*dnx/xbin
        else:
            for nw in xrange(nwin):
                line_read[nw] = VCLOCK*ybin + numhclocks[nw]*HCLOCK + \
                    video*nx[nw]/xbin

        # multiply time to shift one row into serial register by 
        # number of rows for total readout time
        readout = nwin*[0.]
        if isDriftMode:
            readout[0] = (dny/ybin) * line_read[0]
        else:
            for nw in xrange(nwin):
                readout[nw] = (ny[nw]/ybin) * line_read[nw]

        # now get the total time to read out one exposure.
        cycleTime = expose_delay + clear_time + frame_transfer
        if isDriftMode:
            cycleTime += pshift*VCLOCK+yshift[0]+line_clear[0]+readout[0]
        else:
            for nw in xrange(nwin):
                cycleTime += yshift[nw] + line_clear[nw] + readout[nw]

        frameRate = 1.0/cycleTime
        expTime   = expose_delay if lclear else cycleTime - frame_transfer
        deadTime  = cycleTime - expTime
        dutyCycle = 100.0*expTime/cycleTime

        return (expTime, deadTime, cycleTime, dutyCycle, frameRate)

class RunPars(tk.LabelFrame):
    """
    Run parameters
    """
    DTYPES = ('acquisition','science','bias','flat','dark','technical')
        
    def __init__(self, master, share):
        tk.LabelFrame.__init__(self, master, text='Run parameters', 
                               padx=10, pady=10)

        row     = 0
        column  = 0
        tk.Label(self, text='Target name').grid(
            row=row,column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='Programme ID').grid(
            row=row,column=column, sticky=tk.W)
            
        row += 1
        tk.Label(self, 
                 text='Principal Investigator').grid(
            row=row,column=column, sticky=tk.W)
            
        row += 1
        tk.Label(self, text='Observer(s)').grid(
            row=row, column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='Pre-run comment').grid(
            row=row,column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='Data type').grid(
            row=row,column=column, sticky=tk.W+tk.N)
            
        # spacer
        column += 1
        tk.Label(self, text=' ').grid(row=0,column=column)

        # target
        row     = 0
        column += 1
        self.target = drvs.Target(self,share,self.check)
        self.target.grid(row=row, column=column, sticky=tk.W)

        # programme ID
        row += 1
        self.progid = drvs.TextEntry(self, 20, self.check)
        self.progid.grid(row=row, column=column, sticky=tk.W)

        # principal investigator
        row += 1
        self.pi = drvs.TextEntry(self, 20, self.check)
        self.pi.grid(row=row, column=column, sticky=tk.W)

        # observers
        row += 1
        self.observers = drvs.TextEntry(self, 20, self.check)
        self.observers.grid(row=row, column=column, sticky=tk.W)

        # comment
        row += 1
        self.comment = drvs.TextEntry(self, 38)
        self.comment.grid(row=row, column=column, sticky=tk.W)

        # data type
        row += 1
        self.dtype = drvs.Radio(self, RunPars.DTYPES, 3)
        self.dtype.set('undef') 
        self.dtype.grid(row=row,column=column,sticky=tk.W)

        self.share = share

    def check(self, *args):
        """
        Checks the validity of the run parameters. Returns
        flag (True = OK), and a messge which indicates the
        nature of the problem if the flag is False.
        """

        o = self.share
        clog, rlog = o['clog'], o['rlog']

        ok  = True
        msg = ''
        dtype = self.dtype.get()
        if dtype not in RunPars.DTYPES:
            ok = False
            msg += 'No data type has been defined\n'

        if self.target.ok():
            self.target.entry.config(bg=drvs.COL['text_bg'])
        else:
            self.target.entry.config(bg=drvs.COL['error'])
            ok = False
            msg += 'Target name field cannot be blank\n'

        if dtype == 'acquisition' or \
                dtype == 'science' or dtype == 'technical':

            if self.progid.ok():
                self.progid.config(bg=drvs.COL['text_bg'])
            else:
                self.progid.config(bg=drvs.COL['error'])
                ok   = False
                msg += 'Programme ID field cannot be blank\n'

            if self.pi.ok():
                self.pi.config(bg=drvs.COL['text_bg'])
            else:
                self.pi.config(bg=drvs.COL['error'])
                ok   = False
                msg += 'Principal Investigator field cannot be blank\n'

        if self.observers.ok():
            self.observers.config(bg=drvs.COL['text_bg'])
        else:
            self.observers.config(bg=drvs.COL['error'])
            ok   = False
            msg += 'Observers field cannot be blank'

        return (ok,msg)

# Observing section. First a helper routine needed
# by the 'Save' and 'Post' buttons

def createXML(post, cpars, instpars, runpars, clog, rlog):
    """
    This creates the XML representing the current setup. It does
    this by loading a template xml file using directives in the
    configuration parameters, and then imposing the current settings

    Arguments:

      post      : True if posting an application. This is a safety 
                  feature to avoid querying the camera server during a run.
      cpars     : configuration parameters
      instpars  : windows etc
      runpars   : target, PI name etc.
      clog      : command logger
      rlog      : response logger

    Returns a xml.etree.ElementTree.Element
    """

    # identify the template
    appLab = instpars.appLab.value()
    if cpars['debug']:
        print('DEBUG: createXML: application = ' + appLab)
        print('DEBUG: createXML: application vals = ' + str(cpars['templates'][appLab]))

    if cpars['template_from_server']:
        # get template from server
        url = cpars['http_camera_server'] + cpars['http_path_get'] + '?' + \
            cpars['http_search_attr_name'] + '='  + cpars['templates'][appLab]
        if cpars['debug']:
            print ('DEBUG: url = ' + url)
        sxml = urllib2.urlopen(url).read()
        root = ET.fromstring(sxml)
    else:
        # get template from local file
        if cpars['debug']:
            print ('DEBUG: directory = ' + cpars['template_directory'])
        lfile = os.path.join(cpars['template_directory'], 
                             cpars['templates'][appLab]['app'])
        if cpars['debug']:
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
    pdict['X_BIN']['value'] = str(instpars.xbin.value())

    # Y-binning factor
    pdict['Y_BIN']['value'] = str(instpars.ybin.value())

    # Number of exposures
    pdict['NUM_EXPS']['value'] = '-1' if instpars.number.value() == 0 \
        else str(instpars.number.value())

    # LED level
    pdict['LED_FLSH']['value'] = str(instpars.led.value())

    # Avalanche or normal
    pdict['OUTPUT']['value'] = str(instpars.avalanche())

    # Avalanche gain
    pdict['HV_GAIN']['value'] = str(instpars.avgain.value())

    # Clear or not
    pdict['EN_CLR']['value'] = str(instpars.clear())

    # Dwell
    pdict['DWELL']['value'] = str(instpars.expose.value())

    # Readout speed
    pdict['SPEED']['value'] = '0' if instpars.readout == 'Slow' else '1' \
        if instpars.readout == 'Medium' else '2'

    # Number of windows -- needed to set output parameters correctly
    nwin  = int(instpars.nwin.value())

    # Load up enabled windows, null disabled windows
    for nw, win in enumerate(instpars.wframe.wins):
        if nw < nwin:
            pdict['X' + str(nw+1) + '_START']['value'] = str(win.xstart.value())
            pdict['Y' + str(nw+1) + '_START']['value'] = str(win.ystart.value())
            pdict['X' + str(nw+1) + '_SIZE']['value']  = str(win.nx.value())
            pdict['Y' + str(nw+1) + '_SIZE']['value']  = str(win.ny.value())
        else:
            pdict['X' + str(nw+1) + '_START']['value'] = '1'
            pdict['Y' + str(nw+1) + '_START']['value'] = '1'
            pdict['X' + str(nw+1) + '_SIZE']['value']  = '0'
            pdict['Y' + str(nw+1) + '_SIZE']['value']  = '0'

    # Load the user parameters
    uconfig    = root.find('user')
    targ       = ET.SubElement(uconfig, 'target')
    targ.text  = runpars.target.value()
    id         = ET.SubElement(uconfig, 'ID')
    id.text    = runpars.progid.value()
    pi         = ET.SubElement(uconfig, 'PI')
    pi.text    = runpars.pi.value()
    obs        = ET.SubElement(uconfig, 'Observers')
    obs.text   = runpars.observers.value()
    comm       = ET.SubElement(uconfig, 'comment')
    comm.text  = runpars.comment.value()
    dtype      = ET.SubElement(uconfig, 'dtype')
    dtype.text = runpars.dtype.get()
    
    if post:
        if not hasattr(createXML, 'revision'):
            # test for the revision number, only the first time we post
            # to avoid sending a command to the camera while it is going.
            # need to do a pre-post before reading otherwise memory won't 
            # have been set
            try:
                url = cpars['http_camera_server'] + cpars['http_path_exec'] + '?RM,X,0x2E'
                clog.log.info('execCommand, command = "' + command + '"\n')
                response = urllib2.urlopen(url)
                rs  = ReadServer(response.read())
                rlog.log.info('Camera response =\n' + rs.resp() + '\n')        
                if rs.ok:
                    clog.log.info('Response from camera server was OK\n')
                    csfind = rs.root.find('command_status')
                    createXML.revision = int(csfind.attrib['readback'],16)
                else:
                    clog.log.warn('Response from camera server was not OK\n')
                    clog.log.warn('Reason: ' + rs.err + '\n')
                    raise Exception()

            except urllib2.URLError, err:
                clog.log.warn('Failed to get version from camera server\n')
                clog.log.warn(str(err) + '\n')
                raise Exception()

            revision      = ET.SubElement(uconfig, 'revision')
            revision.text = str(createXML.revision)

    return root

class Post(drvs.ActButton):
    """
    Class defining the 'Post' button's operation
    """

    def __init__(self, master, width, share):
        """
        master   : containing widget
        width    : width of button
        share    : other objects 'cpars', 'instpars', 'runpars', 'clog', 'rlog'
        """        
        drvs.ActButton.__init__(self, master, width, share, text='Post')

    def act(self):
        """
        Carries out the action associated with Post button
        """

        o = self.share
        cpars, ipars, rpars, clog, rlog = \
            o['cpars'], o['instpars'], o['runpars'], o['clog'], o['rlog']

        clog.log.info('\nPosting application to servers\n')
        
        # check instrument parameters
        if not ipars.check():
            clog.log.warn('Invalid instrument parameters; post failed.\n')
            tkMessageBox.showwarning('Post failure','Instrument parameters are invalid.')
            return False

        # check run parameters
        rok, msg = rpars.check()
        if not rok:
            clog.log.warn('Invalid run parameters; post failed.\n')
            clog.log.warn(msg + '\n')
            tkMessageBox.showwarning('Post failure','Run parameters are invalid\n' + msg)
            return False

        try:
            # Get XML from template (specific to instrument)
            root = createXML(True, cpars, ipars, rpars, clog, rlog)

            # Post to server
            if drvs.postXML(root, cpars, clog, rlog):
                clog.log.info('Posted application to servers\n')

                # Modify buttons
                self.enable()
                o['Start'].enable()
                o['Stop'].disable()
                o['Post'].enable()
                o['setup'].resetSDSUhard.disable()
                o['setup'].resetSDSUsoft.disable()
                o['setup'].resetPCI.disable()
                o['setup'].setupServers.disable()
                o['setup'].powerOn.disable()
                o['setup'].powerOff.disable()
                return True
            else:
                clog.log.warn('Failed to post application to servers\n')
                return False

        except Exception, err:
            clog.log.warn('Failed to post application to servers\n')
            return False

class Load(drvs.ActButton):
    """
    Class defining the 'Load' button's operation. This loads a previously
    saved configuration from disk.
    """

    def __init__(self, master, width, share):
        """
        master  : containing widget
        width   : width of button
        share   : dictionary of other objects. Must have 'instpars' the instrument
                  setup parameters (windows etc), and 'runpars' the run parameters 
                  (target name etc)
        """
        drvs.ActButton.__init__(self, master, width, share, text='Load')

    def act(self):
        """
        Carries out the action associated with the Load button
        """

        fname = tkFileDialog.askopenfilename(defaultextension='.xml', filetypes=[('xml files', '.xml'),])
        if not fname: 
            share['clog'].warn('Aborted load from disk')
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
        instpars = self.share['instpars']

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
        nwin  = instpars.nwin.value()

        # User parameters ...

        return True

class Save(drvs.ActButton):
    """
    Class defining the 'Save' button's operation. This saves the
    current configuration to disk.
    """

    def __init__(self, master, width, share):
        """
        master  : containing widget
        width   : width of button
        share   : dictionary of other objects. Must have 'cpars' the configuration
                  parameters, 'instpars' the instrument setup parameters (windows etc), 
                  and 'runpars' the run parameters (target name etc), 'clog' and 'rlog'
        """
        drvs.ActButton.__init__(self, master, width, share, text='Save')        

    def act(self):
        """
        Carries out the action associated with the Save button
        """

        o = self.share
        cpars, ipars, rpars, clog, rlog = \
            o['cpars'], o['instpars'], o['runpars'], o['clog'], o['rlog']

        clog.log.info('\nSaving current application to disk\n')

        # check instrument parameters
        if not ipars.check():
            clog.log.warn('Invalid instrument parameters; save failed.\n')
            return False

        # check run parameters
        rok, msg = rpars.check()
        if not rok:
            clog.log.warn('Invalid run parameters; save failed.\n')
            clog.log.warn(msg + '\n')
            return False

        # Get XML from template
        root = createXML(False, cpars, ipars, rpars, clog, rlog)

        # Save to disk
        if drvs.saveXML(root, clog):
            # modify buttons
            o['Load'].enable()
            o['Unfreeze'].disable()

            # unfreeze the instrument params
            ipars.unfreeze()
            return True
        else:
            return False

class Unfreeze(drvs.ActButton):
    """
    Class defining the 'Unfreeze' button's operation. 
    """

    def __init__(self, master, width, share):
        """
        master  : containing widget
        width   : width of button
        share   : dictionary of other objects needed. Needs 'instpars', 
                  the current instrument  parameters to be loaded up once 
                  the template is loaded
        """
        drvs.ActButton.__init__(self, master, width, share, text='Unfreeze')

    def act(self):
        """
        Carries out the action associated with the Unfreeze button
        """
        self.share['instpars'].unfreeze()
        self.share['Load'].enable()
        self.disable()

class Observe(tk.LabelFrame):
    """
    Observe Frame. Collects together buttons that fire off the commands needed
    during observing. These have in common interaction with external objects,
    such as loading data from disk, or sending data to servers. All of these need
    callback routines which are hidden within this class.
    """
    
    def __init__(self, master, share):
        """
        master : container widget
        share   : dictionary of other objects. Must have 'cpars' the configuration
                  parameters, 'instpars' the instrument setup parameters (windows etc), 
                  and 'runpars' the run parameters (target name etc), 'clog' and 'rlog'
        """

        tk.LabelFrame.__init__(self, master, text='Observing commands', padx=10, pady=10)

        # create buttons
        width = 10
        self.load     = Load(self, width, share)
        self.save     = Save(self, width, share)
        self.unfreeze = Unfreeze(self, width, share)
        self.post     = Post(self, width, share)
        self.start    = drvs.Start(self, width, share)
        self.stop     = drvs.Stop(self, width, share)

        # pass all buttons to each other
        share['Load']     = self.load
        share['Save']     = self.save
        share['Unfreeze'] = self.unfreeze
        share['Post']     = self.post
        share['Start']    = self.start
        share['Stop']     = self.stop

        self.share = share

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

        # Implement expert level
        self.setExpertLevel(share['cpars']['expert_level'])

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


class CountsFrame(tk.LabelFrame):
    """
    Frame for count rate estimates
    """
    def __init__(self, master, share):
        """
        master : enclosing widget
        share  : other objects. 'instpars' for timing & binning info.
        """
        tk.LabelFrame.__init__(self, master, pady=2, text='Count & S/N estimator')

        # divide into left and right frames 
        lframe = tk.Frame(self, padx=2)
        rframe = tk.Frame(self, padx=2)

        # entries
        self.filter    = drvs.Radio(lframe, ('u', 'g', 'r', 'i', 'z'), 3, self.checkUpdate)
        self.filter.set('g')
        self.mag       = drvs.RangedFloat(lframe, 18., 0., 30., self.checkUpdate, True, width=5)
        self.seeing    = drvs.RangedFloat(lframe, 1.0, 0.2, 20., self.checkUpdate, True, width=5)
        self.airmass   = drvs.RangedFloat(lframe, 1.5, 1.0, 5.0, self.checkUpdate, True, width=5)
        self.moon      = drvs.Radio(lframe, ('d', 'g', 'b'),  self.checkUpdate)

        # results
        self.expose    = tk.Label(rframe,text='UNDEF',width=11,anchor=tk.W)
        self.duty      = tk.Label(rframe,text='UNDEF',width=11,anchor=tk.W)
        self.peak      = tk.Label(rframe,text='UNDEF',width=11,anchor=tk.W)
        self.total     = tk.Label(rframe,text='UNDEF',width=11,anchor=tk.W)
        self.ston      = tk.Label(rframe,text='UNDEF',width=11,anchor=tk.W)
        self.ston3     = tk.Label(rframe,text='UNDEF',width=11,anchor=tk.W)

        # layout
        # left
        tk.Label(lframe,text='Filter:').grid(
            row=0,column=0,padx=5,pady=3,sticky=tk.W+tk.N)
        self.filter.grid(row=0,column=1,padx=5,pady=3,sticky=tk.W)

        tk.Label(lframe,text='Mag:').grid(
            row=1,column=0,padx=5,pady=3,sticky=tk.W)
        self.mag.grid(row=1,column=1,padx=5,pady=3,sticky=tk.W)

        tk.Label(lframe,text='Seeing:').grid(
            row=2,column=0,padx=5,pady=3,sticky=tk.W)
        self.seeing.grid(row=2,column=1,padx=5,pady=3,sticky=tk.W)

        tk.Label(lframe,text='Airmass:').grid(
            row=3,column=0,padx=5,pady=3,sticky=tk.W)
        self.airmass.grid(row=3,column=1,padx=5,pady=3,sticky=tk.W)

        tk.Label(lframe,text='Moon:').grid(
            row=4,column=0,padx=5,pady=3,sticky=tk.W)
        self.moon.grid(row=4,column=1,padx=5,pady=3,sticky=tk.W)

        # right
        tk.Label(rframe,text='Exposure:').grid(
            row=0,column=0,padx=5,pady=3,sticky=tk.W)
        self.expose.grid(row=0,column=1,padx=5,pady=3,sticky=tk.W)

        tk.Label(rframe,text='Duty cycle:').grid(
            row=1,column=0,padx=5,pady=3,sticky=tk.W)
        self.duty.grid(row=1,column=1,padx=5,pady=3,sticky=tk.W)

        tk.Label(rframe,text='Peak:').grid(
            row=2,column=0,padx=5,pady=3,sticky=tk.W)
        self.peak.grid(row=2,column=1,padx=5,pady=3,sticky=tk.W)

        tk.Label(rframe,text='Total:').grid(
            row=3,column=0,padx=5,pady=3,sticky=tk.W)
        self.total.grid(row=3,column=1,padx=5,pady=3,sticky=tk.W)

        tk.Label(rframe,text='S/N:').grid(
            row=4,column=0,padx=5,pady=3,sticky=tk.W)
        self.ston.grid(row=4,column=1,padx=5,pady=3,sticky=tk.W)

        tk.Label(rframe,text='S/N (3h):').grid(
            row=5,column=0,padx=5,pady=3,sticky=tk.W)
        self.ston3.grid(row=5,column=1,padx=5,pady=3,sticky=tk.W)
        
        # slot frames in
        lframe.grid(row=0,column=0,sticky=tk.W+tk.N)
        rframe.grid(row=0,column=1,sticky=tk.W+tk.N)

        self.share = share

    def checkUpdate(self, *args):
        """
        Updates values after first checking instrument parameters are OK.
        This is not integrated within update to prevent ifinite recursion
        since update gets called from ipars.
        """
        ipars = self.share['instpars']
        if not ipars.check():
            raise drvs.DriverError('drivers.CountsFrame.checkUpdate: invalid parameters')

        self.update(*args)

    def update(self, *args):
        """
        Updates values. You should run a check on the instrument parameters
        before calling this.
        """

        ipars = self.share['instpars']

        expTime, deadTime, cycleTime, dutyCycle, frameRate = ipars.timing()
        total, peak, peakSat, peakWarn, ston, ston3 = self.counts(expTime, cycleTime)

        if expTime < 0.01:
            self.expose.config(text='{0:7.5f} s'.format(expTime))
        elif expTime < 0.1:
            self.expose.config(text='{0:6.4f} s'.format(expTime))
        elif expTime < 1.:
            self.expose.config(text='{0:5.3f} s'.format(expTime))
        elif expTime < 10.:
            self.expose.config(text='{0:4.2f} s'.format(expTime))
        elif expTime < 100.:
            self.expose.config(text='{0:4.1f} s'.format(expTime))
        elif expTime < 1000.:
            self.expose.config(text='{0:4.0f} s'.format(expTime))
        else:
            self.expose.config(text='{0:5.0f} s'.format(expTime))
        self.duty.config(text='{0:4.1f} %'.format(dutyCycle))
        self.peak.config(text='{0:d} cts'.format(int(round(peak))))
        if peakSat:
            self.peak.config(bg=drvs.COL['error'])
        elif peakWarn:
            self.peak.config(bg=drvs.COL['warn'])
        else:
            self.peak.config(bg=drvs.COL['main'])

        self.total.config(text='{0:d} cts'.format(int(round(total))))
        self.ston.config(text='{0:.1f}'.format(ston))
        self.ston3.config(text='{0:.1f}'.format(ston3))

    def counts(self, expTime, cycleTime, ap_scale=1.6):
        """
        Computes counts per pixel, total counts, sky counts
        etc given current magnitude, seeing etc. You should
        run a check on the instrument parameters before calling
        this.

        expTime   : exposure time per frame (seconds)
        cycleTime : sampling, cadence (seconds)
        ap_scale  : aperture radius as multiple of seeing

        Returns: (total, peak, peakSat, peakWarn, ston, ston3)

        total    -- total number of object counts in aperture
        peak     -- peak counts in a pixel
        peakSat  -- flag to indicate saturation
        peakWarn -- flag to indication level approaching saturation
        ston     -- signal-to-noise per exposure
        ston3    -- signal-to-noise after 3 hours on target
        """

        # code directly translated from Java equivalent.
        o = self.share
        ipars, cpars = o['instpars'], o['cpars']
 
        # avalanche mode y/n?
        lnormal = not ipars.avalanche()
		
        # Set the readout speed
        readSpeed = ipars.readSpeed.value()

        if readSpeed == 'Fast':
            video = VIDEO_NORM_FAST if lnormal else VIDEO_AV_FAST
        elif readSpeed == 'Medium':
            video = VIDEO_NORM_MED if lnormal else VIDEO_AV_MED
        elif readSpeed == 'Slow':
            video = VIDEO_NORM_SLOW if lnormal else VIDEO_AV_SLOW
        else:
            raise drvs.DriverError('drivers.CountsFrame.counts: readout speed = ' 
                                   + readSpeed + ' not recognised.')

        xbin   = ipars.xbin.value()	
        ybin   = ipars.ybin.value()	

        # calculate SN info. 
        zero, sky, skyTot, gain, read, darkTot = 0., 0., 0., 0., 0., 0.
        total, peak, correct, signal, readTot, seeing = 0., 0., 0., 0., 0., 0.
        noise,  skyPerPixel, narcsec, npix, signalToNoise3 = 1., 0., 0., 0., 0.

        tinfo   = drvs.TINS[cpars['telins_name']]
        filtnam = self.filter.value()

        zero    = tinfo['zerop'][filtnam]
        mag     = self.mag.value()
        seeing  = self.seeing.value()
        sky     = drvs.SKY[self.moon.value()][filtnam]
        airmass = self.airmass.value()

        # GAIN, RNO
        if readSpeed == 'Fast':
            gain = GAIN_NORM_FAST if lnormal else GAIN_AV_FAST
            read = RNO_NORM_FAST if lnormal else RNO_AV_FAST

        elif readSpeed == 'Medium':
            gain = GAIN_NORM_MED if lnormal else GAIN_AV_MED
            read = RNO_NORM_MED if lnormal else RNO_AV_MED
                    
        elif readSpeed == 'Slow':
            gain = GAIN_NORM_SLOW if lnormal else GAIN_AV_SLOW
            read = RNO_NORM_SLOW if lnormal else RNO_AV_SLOW
                    
        plateScale = tinfo['plateScale']

        # calculate expected electrons 
        total   = 10.**((zero-mag-airmass*drvs.EXTINCTION[filtnam])/2.5)*expTime
        peak    = total*xbin*ybin*(plateScale/(seeing/2.3548))**2/(2.*m.pi)

        # Work out fraction of flux in aperture with radius AP_SCALE*seeing
        correct = 1. - m.exp(-(2.3548*ap_scale)**2/2.)
		    
        # expected sky e- per arcsec
        skyPerArcsec = 10.**((zero-sky)/2.5)*expTime
        skyPerPixel  = skyPerArcsec*plateScale**2*xbin*ybin
        narcsec      = m.pi*(ap_scale*seeing)**2
        skyTot       = skyPerArcsec*narcsec
        npix         = m.pi*(ap_scale*seeing/plateScale)**2/xbin/ybin
                
        signal       = correct*total # in electrons
        darkTot      = npix*DARK_E*expTime  # in electrons
        readTot      = npix*read**2 # in electrons
        cic          = 0 if lnormal else CIC

        # noise, in electrons
        if lnormal:
            noise = m.sqrt(readTot + darkTot + skyTot + signal + cic) 
        else:
            # assume high gain observations in proportional mode
            noise = m.sqrt(readTot/AVALANCHE_GAIN_9**2 + 
                           2.0*(darkTot + skyTot + signal) + cic)
		    
        # Now compute signal-to-noise in 3 hour seconds run
        signalToNoise3 = signal/noise*m.sqrt(3*3600./cycleTime);

        # if using the avalanche mode, check that the signal level 
        # is safe. A single electron entering the avalanche register 
        # results in a distribution of electrons at the output with 
        # mean value given by the parameter avalanche_gain. The 
        # distribution is close to exponential, hence the probability
        # of obtaining an amplification n times higher than the mean is 
        # given by e**-n. A value of 3/5 for n is adopted here for 
        # warning/safety, which will occur once in every ~20/100 
        # amplifications

        # convert from electrons to counts
        total /= gain
        peak  /= gain
        
        warn = 25000
        sat  = 60000

        if not lnormal:
            sat = AVALANCHE_SATURATE/AVALANCHE_GAIN_9/5/gain
            warn = AVALANCHE_SATURATE/AVALANCHE_GAIN_9/3/gain

        peakSat  = peak > sat
        peakWarn = peak > warn

        return (total, peak, peakSat, peakWarn, signal/noise, signalToNoise3)
