#!/usr/bin/env python

"""
uspec provides classes and data specific to ULTRASPEC
"""

from __future__ import print_function
import Tkinter as tk
import tkFont, tkMessageBox, tkFileDialog
import xml.etree.ElementTree as ET
import os, urllib2, math

# mine
import globals as g
import drivers as drvs
import lakeshore as lake
import tcs

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

# avalanche gains assume HVGain = 9. We can adapt this later when we decide
# how gain should be set at TNO. Might be better to make gain a function if
# we allow 0 < HVgain < 9 (SL)

GAIN_NORM_FAST = 0.8    # electrons per count
GAIN_NORM_MED  = 0.7    # electrons per count
GAIN_NORM_SLOW = 0.8    # electrons per count
GAIN_AV_FAST   = 0.0034 # electrons per count
GAIN_AV_MED    = 0.0013 # electrons per count
GAIN_AV_SLOW   = 0.0016 # electrons per count

# Note - avalanche RNO assume HVGain = 9. We can adapt this later when we
# decide how gain should be set at TNO. Might be better to make RNO a function
# if we allow 0 < HVgain < 9 (SL)

RNO_NORM_FAST  =  4.8 # electrons per pixel
RNO_NORM_MED   =  2.8 # electrons per pixel
RNO_NORM_SLOW  =  2.2 # electrons per pixel
RNO_AV_FAST    = 16.5 # electrons per pixel
RNO_AV_MED     =  7.8 # electrons per pixel
RNO_AV_SLOW    =  5.6 # electrons per pixel

# other noise sources
DARK_E         =  0.001 # electrons/pix/sec
CIC            =  0.010 # Clock induced charge, electrons/pix

class InstPars(tk.LabelFrame):
    """
    Ultraspec instrument parameters block.
    """

    def __init__(self, master):
        """
        master : enclosing widget
        """
        tk.LabelFrame.__init__(self, master, text='Instrument parameters',
                               padx=10, pady=10)

        # left hand side
        lhs = tk.Frame(self)

        # Application (mode)
        tk.Label(lhs, text='Mode').grid(row=0,column=0,sticky=tk.W)
        self.app = drvs.Radio(lhs, ('Wins', 'Drift'), 2, self.check,
                              ('Windows', 'Drift'))
        self.app.grid(row=0,column=1,sticky=tk.W)

        # Clear enabled
        self.clearLab = tk.Label(lhs, text='Clear')
        self.clearLab.grid(row=1,column=0, sticky=tk.W)
        self.clear = drvs.OnOff(lhs, True, self.check)
        self.clear.grid(row=1,column=1,sticky=tk.W)

        # Avalanche settings
        tk.Label(lhs, text='Avalanche').grid(row=2,column=0,sticky=tk.W)
        aframe = tk.Frame(lhs)
        self.avalanche = drvs.OnOff(aframe, False, self.check)
        self.avalanche.pack(side=tk.LEFT)
        self.avgainLabel = tk.Label(aframe, text='gain ')
        self.avgainLabel.pack(side=tk.LEFT)
        self.avgain = drvs.RangedInt(aframe, 0, 0, 9, self.check,
                                     False, width=2)
        self.avgain.pack(side=tk.LEFT)
        aframe.grid(row=2,column=1,pady=2,sticky=tk.W)

        # Readout speed
        tk.Label(lhs, text='Readout speed').grid(row=3,column=0, sticky=tk.NW)
        self.readSpeed = drvs.Radio(lhs, ('Slow', 'Medium', 'Fast'), 1,
                                    self.check, ('Slow', 'Medium', 'Fast'))
        self.readSpeed.grid(row=3,column=1,pady=2,sticky=tk.W)

        # Exposure delay
        tk.Label(lhs, text='Exposure delay (s)').grid(row=4,column=0,
                                                      sticky=tk.W)

        elevel = g.cpars['expert_level']
        if elevel == 0:
            self.expose = drvs.Expose(lhs, 0.0007, 0.0007, 1677.7207,
                                      self.check, width=7)
        elif elevel == 1:
            self.expose = drvs.Expose(lhs, 0.0007, 0.0003, 1677.7207,
                                      self.check, width=7)
        else:
            self.expose = drvs.Expose(lhs, 0.0007, 0., 1677.7207,
                                      self.check, width=7)
        self.expose.grid(row=4,column=1,pady=2,sticky=tk.W)

        # Number of exposures
        tk.Label(lhs, text='Num. exposures  ').grid(row=5,column=0, sticky=tk.W)
        self.number = drvs.PosInt(lhs, 1, None, False, width=7)
        self.number.grid(row=5,column=1,pady=2,sticky=tk.W)

        # LED setting
        self.ledLab = tk.Label(lhs, text='LED setting')
        self.ledLab.grid(row=6,column=0, sticky=tk.W)
        self.led = drvs.RangedInt(lhs, 0, 0, 4095, None, False, width=7)
        self.led.grid(row=6,column=1,pady=2,sticky=tk.W)
        self.ledValue = self.led.value()

        # Right-hand side: the window parameters
        rhs = tk.Frame(self)

        # window mode frame (initially full frame)
        xs    = (1,101,201,301)
        xsmin = (1,1,1,1)
        xsmax = (1056,1056,1056,1056)
        ys    = (1,101,201,301)
        ysmin = (1,1,1,1)
        ysmax = (1072,1072,1072,1072)
        nx    = (1056,100,100,100)
        ny    = (1072,100,100,100)
        xbfac = (1,2,3,4,5,6,8)
        ybfac = (1,2,3,4,5,6,8)
        self.wframe = drvs.Windows(rhs, xs, xsmin, xsmax, ys, ysmin, ysmax,
                                   nx, ny, xbfac, ybfac, self.check)
        self.wframe.grid(row=2,column=0,columnspan=3,sticky=tk.W+tk.N)

        # drift mode frame (just one pair)
        xsl    = (100,)
        xslmin = (1,)
        xslmax = (1024,)
        xsr    = (600,)
        xsrmin = (1,)
        xsrmax = (1024,)
        ys     = (1,)
        ysmin  = (1,)
        ysmax  = (1024,)
        nx     = (50,)
        ny     = (50,)
        xbfac  = (1,2,3,4,5,6,8)
        ybfac  = (1,2,3,4,5,6,8)
        self.pframe = drvs.WinPairs(rhs, xsl, xslmin, xslmax, xsr, xsrmin,
                                    xsrmax, ys, ysmin, ysmax, nx, ny,
                                    xbfac, ybfac, self.check)

        # Pack two halfs
        lhs.pack(side=tk.LEFT,anchor=tk.N,padx=5)
        rhs.pack(side=tk.LEFT,anchor=tk.N,padx=5)

        # Store freeze state
        self.frozen = False

        # stores current avalanche setting to check for changes
        self.oldAvalanche = False

        self.setExpertLevel()

    def setExpertLevel(self):
        """
        Modifies widget according to expertise level, which in this
        case is just matter of hiding or revealing the LED option
        and changing the lower limit on the exposure button.
        """

        level = g.cpars['expert_level']
#        print('setting expert level')

        if level == 0:
            self.expose.fmin = 0.0007
            self.ledLab.grid_forget()
            self.led.grid_forget()
            self.ledValue = self.led.value()
            self.led.set(0)

        elif level == 1:
            self.expose.fmin = 0.0003
            self.led.set(self.ledValue)
            self.ledLab.grid(row=6,column=0, sticky=tk.W)
            self.led.grid(row=6,column=1,pady=2,sticky=tk.W)

        elif level == 2:
            self.expose.fmin = 0.0
            self.led.set(self.ledValue)
            self.ledLab.grid(row=6,column=0, sticky=tk.W)
            self.led.grid(row=6,column=1,pady=2,sticky=tk.W)

    def isDrift(self):
        """
        Returns True if we are in drift mode
        """
        if self.app.value() == 'Drift':
            return True
        elif self.app.value() == 'Windows':
            return False
        else:
            raise UspecError('uspec.InstPars.isDrift: application = ' + \
                                 self.app.value() + ' not recognised.')

    def loadXML(self, xml):
        """
        Sets the values of instrument parameters given an
        ElementTree containing suitable XML
        """

        # find application
        xmlid = xml.attrib['id']
        for app, d in g.cpars['templates'].iteritems():
            if xmlid == d['id']:
                break
        else:
            raise drvs.DriverError('Do not recognize application id = ' + xmlid)

        # find parameters
        cconfig = xml.find('configure_camera')
        pdict = {}
        for param in cconfig.findall('set_parameter'):
            pdict[param.attrib['ref']] = param.attrib['value']

        xbin, ybin = int(pdict['X_BIN']), int(pdict['Y_BIN'])

        # Set them.

        # Number of exposures
        self.number.set(pdict['NUM_EXPS'] if pdict['NUM_EXPS'] != '-1' else 0)

        # LED level
        self.led.set(pdict['LED_FLSH'])

        # Avalanche or normal
        self.avalanche.set(pdict['OUTPUT'])

        # Avalanche gain
        self.avgain.set(pdict['HV_GAIN'])

        # Dwell
        self.expose.set(str(float(pdict['DWELL'])/10000.))

        # Readout speed
        speed = pdict['SPEED']
        self.readSpeed.set('Slow' if \
                           speed == '0' else 'Medium' if speed == '1' \
                           else 'Fast')

        if app == 'Windows':
            # Clear or not
            self.clear.set(pdict['EN_CLR'])

            # now for the windows which come in two flavours
            self.app.set('Windows')
            w = self.wframe

            # X-binning factor
            w.xbin.set(xbin)

            # Y-binning factor
            w.ybin.set(ybin)

            # Load up windows
            nwin = 0
            for nw in xrange(4):
                xs = 'X' + str(nw+1) + '_START'
                ys = 'Y' + str(nw+1) + '_START'
                nx = 'X' + str(nw+1) + '_SIZE'
                ny = 'Y' + str(nw+1) + '_SIZE'
                if xs in pdict and ys in pdict and nx in pdict and ny in pdict \
                        and pdict[nx] != '0' and pdict[ny] != 0:
                    xsv, ysv, nxv, nyv = int(pdict[xs]),int(pdict[ys]),int(pdict[nx]),int(pdict[ny])
                    nxv *= xbin
                    nyv *= ybin

                    nchop = max(0,17-xsv)
                    if nchop % xbin != 0:
                        nchop = xbin * (nchop // xbin + 1)

                    if self.avalanche():
                        xsv  = max(1, 1074 - xsv - nxv)
                    else:
                        xsv  = max(1, xsv + nchop - 16)
                    nxv -= nchop

                    w.xs[nw].set(xsv)
                    w.ys[nw].set(ysv)
                    w.nx[nw].set(nxv)
                    w.ny[nw].set(nyv)
                    nwin += 1
                else:
                    break

            # Set the number of windows
            w.nwin.set(nwin)

        else:
            self.clear.set(0)

            # now for drift mode
            self.app.set('Drift')
            p = self.pframe

            # X-binning factor
            p.xbin.set(xbin)

            # Y-binning factor
            p.ybin.set(ybin)

            # Load up window pair values
            xslv, xsrv, ysv, nxv, nyv = int(pdict['X1_START']),int(pdict['X2_START']),\
                int(pdict['Y1_START']),int(pdict['X1_SIZE']),int(pdict['Y1_SIZE'])

            nxv *= xbin
            nyv *= ybin

            nchop = max(0,17-xslv)
            if nchop % xbin != 0:
                nchop = xbin * (nchop // xbin + 1)

            if self.avalanche():
                xslv = max(1,1074-xslv-nxv)
                xsrv = max(1,1074-xsrv-nxv)
            else:
                xslv = max(1,xslv+nchop-16)
                xsrv = max(1,xsrv+nchop-16)

            nxv -= nchop
            if xslv > xsrv:
                xsrv, xslv = xslv, xsrv

            # finally set the values
            p.xsl[0].set(xslv)
            p.xsr[0].set(xsrv)
            p.ys[0].set(ysv)
            p.nx[0].set(nxv)
            p.ny[0].set(nyv)
            p.npair.set(1)

    def check(self, *args):
        """Callback function for running validity checks on the CCD
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

        This can only be run once the 'observe' are defined.
        """
        # Switch visible widget according to the application
        if self.isDrift():
            self.wframe.grid_forget()
            self.pframe.grid(row=2,column=0,columnspan=3,sticky=tk.W+tk.N)
            self.clearLab.config(state='disable')
            if not self.frozen:
                self.clear.config(state='disable')
                self.pframe.enable()
        else:
            self.pframe.grid_forget()
            self.wframe.grid(row=2,column=0,columnspan=3,sticky=tk.W+tk.N)
            self.clearLab.config(state='normal')
            if not self.frozen:
                self.clear.config(state='normal')
                self.wframe.enable()

        if self.avalanche():
            if not self.frozen: self.avgain.enable()
            if not self.oldAvalanche:
                # only update status if there has been a change
                # this is needed because any change to avGain causes
                # this check to be run and we must prevent the gain
                # automatically being set back to zero
                self.avgainLabel.configure(state='normal')
                self.avgain.set(0)
                self.oldAvalanche = True
        else:
            self.avgain.disable()
            self.avgainLabel.configure(state='disable')
            self.oldAvalanche = False

        # check the window settings
        if self.isDrift():
            status = self.pframe.check()
        else:
            status = self.wframe.check()

        # exposure delay
        if self.expose.ok():
            self.expose.config(bg=g.COL['main'])
        else:
            self.expose.config(bg=g.COL['warn'])
            status = False

        # allow posting according to whether the parameters are ok
        # update count and S/N estimates as well
        if status:
            if g.cpars['cdf_servers_on'] and \
                    g.cpars['servers_initialised'] and \
                    not drvs.isRunActive():
                g.observe.start.enable()
            g.count.update()
        else:
            g.observe.start.disable()

        return status

    def freeze(self):
        """
        Freeze all settings so that they can't be altered
        """
        self.app.disable()
        self.clear.disable()
        self.avalanche.disable()
        self.avgain.disable()
        self.readSpeed.disable()
        self.led.disable()
        self.expose.disable()
        self.number.disable()
        self.wframe.freeze()
        self.pframe.freeze()
        self.frozen = True

    def unfreeze(self):
        """
        Reverse of freeze
        """
        self.app.enable()
        self.clear.enable()
        self.avalanche.enable()
        self.readSpeed.enable()
        self.led.enable()
        self.expose.enable()
        self.number.enable()
        self.wframe.unfreeze()
        self.pframe.unfreeze()
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
            xbin = self.wframe.xbin.value()
            ybin = self.wframe.ybin.value()
            if self.app.value() == 'Windows':
                nwin = self.wframe.nwin.value()
                ret  = str(xbin) + ' ' + str(ybin) + ' ' + str(nwin) + '\r\n'
                for xs, ys, nx, ny in self.wframe:
                    ret   += str(xs) + ' ' + str(ys) + ' ' + str(nx) + ' ' + \
                        str(ny) + '\r\n'
            elif self.app.value() == 'Drift':
                nwin = 2*self.wframe.npair.value()
                ret  = str(xbin) + ' ' + str(ybin) + ' ' + str(nwin) + '\r\n'
                for xsl, xsr, ys, nx, ny in self.pframe:
                    ret   += str(xsl) + ' ' + str(ys) + ' ' + str(nx) + ' ' + \
                        str(ny) + '\r\n'
                    ret   += str(xsr) + ' ' + str(ys) + ' ' + str(nx) + ' ' + \
                        str(ny) + '\r\n'

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
        HCLOCK  = HCLOCK_NORM if lnormal else HCLOCK_AV

        # drift mode y/n?
        isDriftMode = self.app.value() == 'Drift'

        # Set the readout speed
        readSpeed = self.readSpeed.value()

        if readSpeed == 'Fast':
            video = VIDEO_NORM_FAST if lnormal else VIDEO_AV_FAST
        elif readSpeed == 'Medium':
            video = VIDEO_NORM_MED if lnormal else VIDEO_AV_MED
        elif readSpeed == 'Slow':
            video = VIDEO_NORM_SLOW if lnormal else VIDEO_AV_SLOW
        else:
            raise UspecError('uspec.InstPars.timing: readout speed = ' \
                                 + readSpeed + ' not recognised.')

        # clear chip on/off?
        lclear = not isDriftMode and self.clear()

        # get exposure delay
        expose = self.expose.value()

        # window parameters
        if isDriftMode:
            xbin    = self.pframe.xbin.value()
            ybin    = self.pframe.ybin.value()
            dxleft  = self.pframe.xsl[0].value()
            dxright = self.pframe.xsr[0].value()
            dys     = self.pframe.ys[0].value()
            dnx     = self.pframe.nx[0].value()
            dny     = self.pframe.ny[0].value()
        else:
            xbin   = self.wframe.xbin.value()
            ybin   = self.wframe.ybin.value()
            xs, ys, nx, ny = [], [], [], []
            nwin = self.wframe.nwin.value()
            for xsv, ysv, nxv, nyv in self.wframe:
                xs.append(xsv)
                ys.append(ysv)
                nx.append(nxv)
                ny.append(nyv)

        if lnormal:
            # normal mode convert xs by ignoring 16 overscan pixel
            if isDriftMode:
                dxleft  += 16
                dxright += 16
            else:
                for nw in xrange(nwin):
                    xs[nw] += 16
        else:
            if isDriftMode:
                dxright = FFX - (dxright-1) - (dnx-1)
                dxleft  = FFX - (dxleft-1) - (dnx-1)

                # in drift mode, also need to swap the windows around
                dxright, dxleft = dxleft, dxright
            else:
                # in avalanche mode, need to swap windows around
                for nw in xrange(nwin):
                    xs[nw] = FFX - (xs[nw]-1) - (nx[nw]-1)

        # convert timing parameters to seconds
        expose_delay = expose

        # clear chip by VCLOCK-ing the image and storage areas
        if lclear:
            # accomodate changes to clearing made by DA to fix dark current
            # when clearing charge along normal output
            clear_time = 2.0*(FFY*VCLOCK+39.e-6) + FFX*HCLOCK_NORM + \
                2162.0*HCLOCK_AV
        else:
            clear_time = 0.0

        hclockFactor = 1.0 if lnormal else 2.0

        if isDriftMode:
            # for drift mode, we need the number of windows in the pipeline
            # and the pipeshift
            pnwin  = int(((1037. / dny) + 1.)/2.)
            pshift = 1037.- (2.*pnwin-1.)*dny
            frame_transfer = (dny+dys-1.)*VCLOCK + 49.0e-6

            yshift   = [0.]
            yshift[0]=(dys-1.0)*VCLOCK

            # After placing the window adjacent to the serial register, the
            # register must be cleared by clocking out the entire register,
            # taking FFX hclocks (we no longer open the dump gates, which
            # took only 8 hclock cycles to complete, but gave ramps and
            # bright rows in the bias). We think dave does 2*FFX hclocks
            # in avalanche mode, but need to check this with him.
            line_clear = [0.]
            if yshift[0] != 0:
                line_clear[0] = hclockFactor*FFX*HCLOCK

            numhclocks = [0]
            numhclocks[0] = FFX
            if not lnormal:
                numhclocks[0] += AVALANCHE_PIXELS

            line_read = [0.]
            line_read[0] = VCLOCK*ybin + numhclocks[0]*HCLOCK + \
                video*2.0*dnx/xbin

            readout = [0.]
            readout[0] = (dny/ybin) * line_read[0]

        else:
            # If not drift mode, move entire image into storage area
            # the -35 component is because Derek only shifts 1037 pixels
            # (composed of 1024 active rows, 5 dark reference rows, 2
            # transition rows and 6 extra overscan rows for good measure)
            # If drift mode, just move the window into the storage area
            frame_transfer = (FFY-35)*VCLOCK + 49.0e-6

            yshift = nwin*[0.]
            yshift[0]=(ys[0]-1.0)*VCLOCK
            for nw in xrange(1,nwin):
                yshift[nw] = (ys[nw]-ys[nw-1]-ny[nw-1])*VCLOCK

            line_clear = nwin*[0.]
            for nw in xrange(nwin):
                if yshift[nw] != 0:
                    line_clear[nw] = hclockFactor*FFX*HCLOCK

            # calculate how long it takes to shift one row into the serial
            # register shift along serial register and then read out the data.
            # The charge in a row after a window used to be dumped, taking
            # 8 HCLOCK cycles. This created ramps and bright rows/columns in
            # the images, so was removed.
            numhclocks = nwin*[0]
            for nw in xrange(nwin):
                numhclocks[nw] = FFX;
                if not lnormal:
                    numhclocks[nw] += AVALANCHE_PIXELS

            line_read = nwin*[0.]
            for nw in xrange(nwin):
                line_read[nw] = VCLOCK*ybin + numhclocks[nw]*HCLOCK + \
                    video*nx[nw]/xbin

            # multiply time to shift one row into serial register by
            # number of rows for total readout time
            readout = nwin*[0.]
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
    DTYPES = ('data', 'acquire', 'bias', 'flat', 'dark', 'tech')
    DVALS  = ('data', 'data caution', 'bias', 'flat', 'dark', 'technical')

    def __init__(self, master):
        tk.LabelFrame.__init__(self, master, text='Next run parameters',
                               padx=10, pady=10)

        row     = 0
        column  = 0
        tk.Label(self, text='Target name').grid(
            row=row,column=column, sticky=tk.W)

        row += 1
        tk.Label(self, text='Filter').grid(
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
        self.target = drvs.Target(self, self.check)
        self.target.grid(row=row, column=column, sticky=tk.W)

        # filter
        row += 1
        self.filter = drvs.Radio(self, g.cpars['active_filter_names'], 6)
        self.filter.set('UNDEF')
        self.filter.grid(row=row,column=column,sticky=tk.W)

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
        self.dtype = drvs.Radio(self, RunPars.DTYPES, 3, self.check,
                                values=RunPars.DVALS)
        self.dtype.set('UNDEF')
        self.dtype.grid(row=row,column=column,sticky=tk.W)

    def loadXML(self, xml):
        """
        Sets the values of the run parameters given an ElementTree
        containing suitable XML
        """
        user  = xml.find('user')

        def getUser(user, param):
           val = user.find(param)
           if val is None or val.text is None:
               return ''
           else:
               return val.text

        self.target.set(getUser(user,'target'))
        self.progid.set(getUser(user,'ID'))
        self.pi.set(getUser(user,'PI'))
        self.observers.set(getUser(user,'Observers'))
        self.comment.set(getUser(user,'comment'))
        self.dtype.set(getUser(user,'flags'))
        self.filter.set(getUser(user,'filters'))

    def check(self, *args):
        """
        Checks the validity of the run parameters. Returns
        flag (True = OK), and a message which indicates the
        nature of the problem if the flag is False.
        """

        ok  = True
        msg = ''

        if self.dtype.value() == 'bias' or self.dtype.value() == 'flat' or \
           self.dtype.value() == 'dark':
            self.pi.configure(state='disable')
            self.progid.configure(state='disable')
            self.target.disable()
        else:
            self.pi.configure(state='normal')
            self.progid.configure(state='normal')
            self.target.enable()

        if g.cpars['require_run_params']:
            dtype = self.dtype.value()
            if dtype not in RunPars.DVALS:
                ok = False
                msg += 'No data type has been defined\n'

            if self.target.ok():
                self.target.entry.config(bg=g.COL['main'])
            else:
                self.target.entry.config(bg=g.COL['error'])
                ok = False
                msg += 'Target name field cannot be blank\n'

            if dtype == 'data caution' or \
               dtype == 'data' or dtype == 'technical':

                if self.progid.ok():
                    self.progid.config(bg=g.COL['main'])
                else:
                    self.progid.config(bg=g.COL['error'])
                    ok   = False
                    msg += 'Programme ID field cannot be blank\n'

                if self.pi.ok():
                    self.pi.config(bg=g.COL['main'])
                else:
                    self.pi.config(bg=g.COL['error'])
                    ok   = False
                    msg += 'Principal Investigator field cannot be blank\n'

            if self.observers.ok():
                self.observers.config(bg=g.COL['main'])
            else:
                self.observers.config(bg=g.COL['error'])
                ok   = False
                msg += 'Observers field cannot be blank'

        return (ok,msg)

    def freeze(self):
        """
        Freeze all settings so that they can't be altered
        """
        self.target.disable()
        self.filter.disable()
        self.progid.configure(state='disable')
        self.pi.configure(state='disable')
        self.observers.configure(state='disable')
        self.comment.configure(state='disable')
        self.dtype.disable()

    def unfreeze(self):
        """
        Unfreeze all settings so that they can be altered
        """
        self.filter.enable()
        dtype = self.dtype.value()
        if dtype == 'data caution' or dtype == 'data' or dtype == 'technical':
            self.progid.configure(state='normal')
            self.pi.configure(state='normal')
            self.target.enable()
        self.observers.configure(state='normal')
        self.comment.configure(state='normal')
        self.dtype.enable()

# Observing section. First a helper routine needed
# by the 'Save' and 'Start' buttons

def createXML(post):
    """
    This creates the XML representing the current setup. It does
    this by loading a template xml file using directives in the
    configuration parameters, and then imposing the current settings

    Arguments:

      post      : True if posting an application. This is a safety
                  feature to avoid querying the camera server during a run.

    Returns an xml.etree.ElementTree.Element
    """
    # identify the template
    app = g.ipars.app.value()
    g.clog.debug('createXML: application = ' + app)
    g.clog.debug('createXML: application vals = ' + \
                     str(g.cpars['templates'][app]))

    if g.cpars['template_from_server']:
        # get template from server
        url = g.cpars['http_camera_server'] + g.HTTP_PATH_GET + '?' + \
              g.HTTP_SEARCH_ATTR_NAME + '=' + g.cpars['templates'][app]['app']
        g.clog.debug('url = ' + url)
        sxml = urllib2.urlopen(url).read()
        root = ET.fromstring(sxml)

    else:
        # get template from local file
        g.clog.debug('directory = ' + g.cpars['template_directory'])

        lfile = os.path.join(g.cpars['template_directory'],
                             g.cpars['templates'][app]['app'])
        g.clog.debug('local file = ' + lfile)
        tree = ET.parse(lfile)
        root = tree.getroot()

    # Find all CCD parameters
    cconfig = root.find('configure_camera')
    pdict = {}
    for param in cconfig.findall('set_parameter'):
        pdict[param.attrib['ref']] = param.attrib

    # Set them. This is designed so that missing
    # parameters will cause exceptions to be raised.

    # Number of exposures
    pdict['NUM_EXPS']['value'] = '-1' if g.ipars.number.value() == 0 \
        else str(g.ipars.number.value())

    # LED level
    pdict['LED_FLSH']['value'] = str(g.ipars.led.value())

    # Avalanche or normal
    pdict['OUTPUT']['value'] = str(g.ipars.avalanche())

    # Avalanche gain
    pdict['HV_GAIN']['value'] = str(g.ipars.avgain.value())

    # Dwell
    pdict['DWELL']['value'] = str(g.ipars.expose.ivalue())

    # Readout speed
    pdict['SPEED']['value'] = '0' if g.ipars.readSpeed.value() == 'Slow' \
        else '1' if g.ipars.readSpeed.value() == 'Medium' else '2'

    # Find the user parameters
    uconfig    = root.find('user')

    if app == 'Windows':
        # Clear or not
        pdict['EN_CLR']['value'] = str(g.ipars.clear())

        w = g.ipars.wframe

        # Number of windows -- needed to set output parameters correctly
        nwin  = w.nwin.value()

        xbin, ybin = w.xbin.value(), w.ybin.value()

        # X-binning factor
        pdict['X_BIN']['value'] = str(xbin)

        # Y-binning factor
        pdict['Y_BIN']['value'] = str(ybin)

        # Load up enabled windows, null disabled windows
        npix = 0
        for nw in xrange(nwin):
            xs, ys, nx, ny = w.xs[nw].value(), w.ys[nw].value(), \
                w.nx[nw].value(), w.ny[nw].value()

            # save for Vik's autologger
            xstart = ET.SubElement(uconfig, 'X' + str(nw+1) + '_START')
            xstart.text  = str(xs)

            # re-jig so that user always refers to same part of
            # the CCD regardless of the output being used. 'Derek coords'
            xs = 1074 - xs - nx if g.ipars.avalanche() else xs + 16
            pdict['X' + str(nw+1) + '_START']['value'] = str(xs)
            pdict['Y' + str(nw+1) + '_START']['value'] = str(ys)
            pdict['X' + str(nw+1) + '_SIZE']['value']  = str(nx // xbin)
            pdict['Y' + str(nw+1) + '_SIZE']['value']  = str(ny // ybin)
            npix += (nx // xbin)*(ny // ybin)


        for nw in xrange(nwin,4):
            pdict['X' + str(nw+1) + '_START']['value'] = '1'
            pdict['Y' + str(nw+1) + '_START']['value'] = '1'
            pdict['X' + str(nw+1) + '_SIZE']['value']  = '0'
            pdict['Y' + str(nw+1) + '_SIZE']['value']  = '0'

    else:

        p = g.ipars.pframe

        # Number of windows -- needed to set output parameters correctly
        # although WinPairs supports multiple pairs, only one is allowed
        # in drift mode.
        npair = p.npair.value()
        if npair != 1:
            g.clog.warn('Only one pair of drift mode windows supported.')
            raise Exception()

        xbin, ybin = p.xbin.value(), p.ybin.value()

        # X-binning factor
        pdict['X_BIN']['value'] = str(xbin)

        # Y-binning factor
        pdict['Y_BIN']['value'] = str(ybin)

        xsl, xsr, ys, nx, ny = p.xsl[0].value(), p.xsr[0].value(), \
            p.ys[0].value(), p.nx[0].value(), p.ny[0].value()

        # save for Vik's autologger
        x1start = ET.SubElement(uconfig, 'X1_START')
        x1start.text  = str(xsl)
        x2start = ET.SubElement(uconfig, 'X2_START')
        x2start.text  = str(xsr)

        # re-jig so that user always refers to same part of
        # the CCD regardless of the output being used. 'Derek coords'
        if g.ipars.avalanche():
            xsl = 1074 - xsl - nx
            xsr = 1074 - xsr - nx
        else:
            xsl += 16
            xsr += 16

        if xsl > xsr:
            xsr, xsl = xsl, xsr

        # note we make X dimensions same for each window
        # although this is not strictly required
        pdict['X1_START']['value'] = str(xsl)
        pdict['X2_START']['value'] = str(xsr)
        pdict['X1_SIZE']['value']  = str(nx // xbin)
        pdict['X2_SIZE']['value']  = str(nx // xbin)
        pdict['Y1_START']['value'] = str(ys)
        pdict['Y1_SIZE']['value']  = str(ny // ybin)
        npix = 2*(nx // xbin)*(ny // ybin)

    pdict['X_SIZE']['value']  = str(npix)
    pdict['Y_SIZE']['value']  = '1'

    flag = g.rpars.dtype.value()
    if flag == 'bias':
        target_str = 'Bias'
        pi_str     = 'Calib'
        progid_str = 'Calib'
    elif flag == 'dark':
        target_str = 'Dark'
        pi_str     = 'Calib'
        progid_str = 'Calib'
    elif flag == 'technical':
        target_str = g.rpars.target.value()
        pi_str     = 'Calib'
        progid_str = 'Calib'
    elif flag == 'flat':
        target_str = 'Flat'
        pi_str     = 'Calib'
        progid_str = 'Calib'
    else:
        target_str = g.rpars.target.value()
        pi_str     = g.rpars.pi.value()
        progid_str = g.rpars.progid.value()

    targ       = ET.SubElement(uconfig, 'target')
    targ.text  = target_str
    id         = ET.SubElement(uconfig, 'ID')
    id.text    = progid_str
    pi         = ET.SubElement(uconfig, 'PI')
    pi.text    = pi_str
    obs        = ET.SubElement(uconfig, 'Observers')
    obs.text   = g.rpars.observers.value()
    comm       = ET.SubElement(uconfig, 'comment')
    comm.text  = g.rpars.comment.value()
    dtype      = ET.SubElement(uconfig, 'flags')
    dtype.text = flag
    filtr      = ET.SubElement(uconfig, 'filters')
    filtr.text = g.rpars.filter.value()

    if post:
        if not hasattr(createXML, 'revision'):
            # test for the revision number, only the first time we post
            # to avoid sending a command to the camera while it is going.
            # need to do a pre-post before reading otherwise memory won't
            # have been set
            try:
                url = g.cpars['http_camera_server'] + g.HTTP_PATH_EXEC + \
                    '?RM,X,0x2E'
                g.clog.info('exec = "' + url + '"')
                response = urllib2.urlopen(url)
                rs = drvs.ReadServer(response.read())
                g.rlog.info('Camera response =\n' + rs.resp())
                if rs.ok:
                    g.clog.info('Response from camera server was OK')
                    csfind = rs.root.find('command_status')
                    createXML.revision = int(csfind.attrib['readback'],16)
                else:
                    g.clog.warn('Response from camera server was not OK')
                    g.clog.warn('Reason: ' + rs.err)
                    raise Exception()

            except urllib2.URLError, err:
                g.clog.warn('Failed to get version from camera server')
                g.clog.warn(str(err))
                raise Exception()

        revision      = ET.SubElement(uconfig, 'revision')
        revision.text = str(createXML.revision)

    # finally return with the XML
    return root

class Start(drvs.ActButton):
    """
    Class defining the 'Start' button's operation. This carries out
    both the old Post and Start buttons' operation in one. This involves:

    -- checking that the instrument and run parameters are OK
    -- (optionally) querying when the target has changed or avalanche gain on
    -- (optionally) looking for TCS information
    -- changes the filter if need be.
    -- creating the application from a template given current settings
    -- posting it to the servers
    -- starting the run
    -- setting buttons appropriately
    -- starting the exposure timer.
    """

    def __init__(self, master, width):
        """
        master   : containing widget
        width    : width of button
        """

        drvs.ActButton.__init__(self, master, width, bg=g.COL['start'],
                                text='Start')
        self.target = None

    def enable(self):
        """
        Enable the button.
        """
        drvs.ActButton.enable(self)
        self.config(bg=g.COL['start'])

    def disable(self):
        """
        Disable the button, if in non-expert mode.
        """
        drvs.ActButton.disable(self)
        if self._expert:
            self.config(bg=g.COL['start'])
        else:
            self.config(bg=g.COL['startD'])

    def setExpert(self):
        """
        Turns on 'expert' status whereby the button is always enabled,
        regardless of its activity status.
        """
        drvs.ActButton.setExpert(self)
        self.config(bg=g.COL['start'])

    def setNonExpert(self):
        """
        Turns off 'expert' status whereby to allow a button to be disabled
        """
        self._expert = False
        if self._active:
            self.enable()
        else:
            self.disable()

    def act(self):
        """
        Carries out the action associated with Start button
        """

        # Check the instrument parameters
        if not g.ipars.check():
            g.clog.warn('Invalid instrument parameters.')
            tkMessageBox.showwarning('Start failure',
                                     'Please check the instrument setup.')
            return False

        # Check the run parameters
        rok, msg = g.rpars.check()
        if not rok:
            g.clog.warn('Invalid run parameters.')
            g.clog.warn(msg)
            tkMessageBox.showwarning('Start failure',
                                     'Please check the run parameters:\n' + msg)
            return False

        # Confirm when avalanche gain is on
        if g.cpars['expert_level'] == 0 and g.cpars['confirm_hv_gain_on'] and \
                g.ipars.avalanche() and g.ipars.avgain.value() > 0:

            if not tkMessageBox.askokcancel(
                'Avalanche','Avalanche gain is on at level = ' +
                str(g.ipars.avgain.value()) + '\n' + 'Continue?'):
                g.clog.warn('Start operation cancelled')
                return False

        # Confirm when the target name has changed
        if g.cpars['expert_level'] == 0 and g.cpars['confirm_on_change'] and \
                self.target is not None and \
                self.target != g.rpars.target.value():

            if not tkMessageBox.askokcancel(
                'Confirm target', 'Target name has changed\n' +
                 'Continue?'):
                g.clog.warn('Start operation cancelled')
                return False


        try:
            # Get XML from template and modify according to the
            # current settings
            root = createXML(True)

            # locate user stuff
            uconfig    = root.find('user')

            if g.cpars['tcs_on']:
                # get positional info from telescope
                if g.cpars['telins_name'] == 'TNO-USPEC':
                    try:
                        ra,dec,pa,focus,tracking,epa = tcs.getTntTcs()
                        if not g.info.tracking and \
                                not tkMessageBox.askokcancel(
                            'TCS error',
                            'The telescope does not appear to be tracking and the\n' +
                            'RA, Dec and/or PA could be wrong as a result.\n\n' +
                            'Do you want to continue with the run?'):
                            g.clog.warn('Start operation cancelled')
                            return False
                        elif tracking == 'disabled' and \
                                not tkMessageBox.askokcancel(
                            'TCS error',
                            'The TCS server says that tracking is disabled. The RA, Dec\n' +
                            'and PA are probably wrong (and possibly frozen) as a result.\n' +
                            'Please check on the TCS server with NARIT staff.\n\n' +
                            'Do you want to continue with the run?'):
                            g.clog.warn('Start operation cancelled')
                            return False

                        # log the tracking
                        g.clog.debug('At run start, tracking = ' + tracking)

                        # all systems are go...
                        tra         = ET.SubElement(uconfig, 'RA')
                        tra.text    = drvs.d2hms(ra/15., 1, False)
                        tdec        = ET.SubElement(uconfig, 'Dec')
                        tdec.text   = drvs.d2hms(dec, 0, True)
                        tpa         = ET.SubElement(uconfig, 'PA')
                        tpa.text    = '{0:6.2f}'.format(pa)
                        tfocus      = ET.SubElement(uconfig, 'Focus')
                        tfocus.text = '{0:+6.2f}'.format(focus)
                        tepa        = ET.SubElement(uconfig, 'Eng_PA')
                        tepa.text   = '{0:+7.2f}'.format(epa)
                        tracking    = ET.SubElement(uconfig, 'Tracking')
                        tracking.text = 'yes' if g.info.tracking else 'no'
                        ttflag      = ET.SubElement(uconfig, 'TTflag')
                        ttflag.text = tracking

                    except Exception, err:
                        g.clog.warn(err)
                        if not tkMessageBox.askokcancel(
                            'TCS error',
                            'Could not get RA, Dec from telescope.\n' +
                            'Continue?'):
                            g.clog.warn('Start operation cancelled')
                            return False
                else:
                    if not tkMessageBox.askokcancel(
                        'TCS error',
                        'No TCS routine for telescope/instrument = ' +
                        g.cpars['telins_name'] + '\n' +
                        'Could not get RA, Dec from telescope.\n' +
                        'Continue?'):
                        g.clog.warn('Start operation cancelled')
                        return False

            # Change the filter if necessary. Try to connect to the
            # wheel. Raises an Exception if no wheel available
            if not g.wheel.connected:
                g.wheel.connect()

            if not g.wheel.initialised:
                g.wheel.init()

            currentPosition = g.wheel.getPos()
            desiredPosition = g.rpars.filter.getIndex() + 1

            if currentPosition != desiredPosition:
                # We must change the filter before starting the run. This means
                # that we also have to update the filters element of the 'user'
                # part of the xml
                g.clog.info(
                    'Changing filter from "' + \
                    g.cpars['active_filter_names'][currentPosition-1] + \
                    '" to "' + \
                    g.cpars['active_filter_names'][desiredPosition-1] + \
                    '"')
                g.wheel.goto(desiredPosition)
                g.wheel.close()
                current_filter = g.cpars['active_filter_names'][desiredPosition-1]

                # update the XML
                filtr      = uconfig.find('filters')
                filtr.text = current_filter

            else:
                # No action needed
                g.clog.info('No filter change needed')
                g.wheel.close()
                current_filter = g.cpars['active_filter_names'][currentPosition-1]

            # Set position of slide
            pos_ms,pos_mm,pos_px = g.fpslide.slide.return_position()
            fpslide = ET.SubElement(uconfig, 'SlidePos')
            fpslide.text = '{0:d}'.format(int(round(pos_px)))

            # Attempt to get CCD temperature data. Abort if it fails and
            # the Lakeshore is said to be working.
            ccd_temp = ET.SubElement(uconfig, 'ccd_temp')
            finger_temp = ET.SubElement(uconfig, 'finger_temp')
            heater_percent = ET.SubElement(uconfig, 'heater_percent')

            try:
                if g.lakeshore is None:
                    g.lakeshore = lake.LakeFile()

                tempa, tempb, heater = g.lakeshore.temps()
                ccd_temp.text = '{0:5.1f}'.format(tempa)
                finger_temp.text = '{0:5.1f}'.format(tempb)
                heater_percent.text = '{0:4.1f}'.format(heater)

            except:
                if g.cpars['ccd_temperature_on']:
                    raise
                else:
                    g.clog.warn('Failed to read temperature but will start anyway.')
                    g.clog.warn(str(err))
                    ccd_temp.text = 'UNDEF'
                    finger_temp.text = 'UNDEF'
                    heater_percent.text = 'UNDEF'

            # Post the XML it to the server
            g.clog.info('Posting application to the servers')

            if drvs.postXML(root):
                g.clog.info('Post successful; starting run')

                if drvs.execCommand('GO'):
                    # start the exposure timer
                    g.info.timer.start()

                    g.clog.info('Run started on target = ' + \
                                    g.rpars.target.value())

                    # configure buttons
                    self.disable()
                    g.observe.stop.enable()
                    g.observe.load.disable()
                    g.observe.unfreeze.enable()
                    g.setup.resetSDSUhard.disable()
                    g.setup.resetSDSUsoft.disable()
                    g.setup.resetPCI.disable()
                    g.setup.setupServers.disable()
                    g.setup.powerOn.disable()
                    g.setup.powerOff.disable()

                    # freeze instrument and run parameters
                    g.ipars.freeze()
                    g.rpars.freeze()

                    # update the run number
                    try:
                        run  = int(g.info.run.cget('text'))
                        run += 1
                        g.info.run.configure(text='{0:03d}'.format(run))
                    except Exception, err:
                        g.clog.warn('Failed to update run number')

                    # take it that if we have successfully started a
                    # run then we have also initialised the
                    # servers. This is necessary to account for when
                    # one starts usdriver with the servers already
                    # initialised. Rather than re-initialising and
                    # hence incurring another poweron, one can switch
                    # to expert mode and start a run and hence make it
                    # look as though the servers have been
                    # initialised.
                    g.cpars['servers_initialised'] = True

                    # store filter name for use by InfoFrame
                    g.start_filter = current_filter

                    return True
                else:
                    g.clog.warn('Failed to start run')
                    return False
            else:
                g.clog.warn('Failed to post the application')
                return False

        except Exception, err:
            g.clog.warn('Failed to start run')
            g.clog.warn(str(err))
            return False

class Load(drvs.ActButton):
    """
    Class defining the 'Load' button's operation. This loads a previously
    saved configuration from disk.
    """

    def __init__(self, master, width):
        """
        master  : containing widget
        width   : width of button
        """
        drvs.ActButton.__init__(self, master, width, text='Load')

    def act(self):
        """
        Carries out the action associated with the Load button
        """

        fname = tkFileDialog.askopenfilename(
            defaultextension='.xml', filetypes=[('xml files', '.xml'),],
            initialdir=g.cpars['app_directory'])
        if not fname:
            g.clog.warn('Aborted load from disk')
            return False

        # load XML
        tree = ET.parse(fname)
        root = tree.getroot()

        # load up the instrument settings
        g.ipars.loadXML(root)

        # load up the run parameters
        g.rpars.loadXML(root)

        return True

class Save(drvs.ActButton):
    """
    Class defining the 'Save' button's operation. This saves the
    current configuration to disk.
    """

    def __init__(self, master, width):
        """
        master  : containing widget
        width   : width of button
        """
        drvs.ActButton.__init__(self, master, width, text='Save')

    def act(self):
        """
        Carries out the action associated with the Save button
        """
        g.clog.info('\nSaving current application to disk')

        # check instrument parameters
        if not g.ipars.check():
            g.clog.warn('Invalid instrument parameters; save failed.')
            return False

        # check run parameters
        rok, msg = g.rpars.check()
        if not rok:
            g.clog.warn('Invalid run parameters; save failed.')
            g.clog.warn(msg)
            return False

        # Get XML from template
        root = createXML(False)

        # Save to disk
        if drvs.saveXML(root):
            # modify buttons
            g.observe.load.enable()
            g.observe.unfreeze.disable()

            # unfreeze the instrument and run params
            g.ipars.unfreeze()
            g.rpars.unfreeze()
            return True
        else:
            return False

class Unfreeze(drvs.ActButton):
    """
    Class defining the 'Unfreeze' button's operation.
    """

    def __init__(self, master, width):
        """
        master  : containing widget
        width   : width of button
        """
        drvs.ActButton.__init__(self, master, width, text='Unfreeze')

    def act(self):
        """
        Carries out the action associated with the Unfreeze button
        """
        g.ipars.unfreeze()
        g.rpars.unfreeze()
        g.observe.load.enable()
        self.disable()

class Observe(tk.LabelFrame):
    """
    Observe widget. Collects together buttons that fire off the commands needed
    during observing. These have in common interaction with external objects,
    such as loading data from disk, or sending data to servers.
    """

    def __init__(self, master):
        """
        master : container widget
        """

        tk.LabelFrame.__init__(
            self, master, text='Observing commands', padx=10, pady=10)

        # create buttons
        width = 10
        self.load     = Load(self, width)
        self.save     = Save(self, width)
        self.unfreeze = Unfreeze(self, width)
        self.start    = Start(self, width)
        self.stop     = drvs.Stop(self, width)

        # Lay them out
        self.load.grid(row=0,column=0)
        self.save.grid(row=1,column=0)
        self.unfreeze.grid(row=2,column=0)
        self.start.grid(row=0,column=1)
        self.stop.grid(row=1,column=1)

        # Define initial status
        self.start.disable()
        self.stop.disable()
        self.unfreeze.disable()

        # Implement expert level
        self.setExpertLevel()

    def setExpertLevel(self):
        """
        Set expert level
        """
        level = g.cpars['expert_level']

        # now set whether buttons are permanently enabled or not
        if level == 0 or level == 1:
            self.load.setNonExpert()
            self.save.setNonExpert()
            self.unfreeze.setNonExpert()
            self.start.setNonExpert()
            self.stop.setNonExpert()

        elif level == 2:
            self.load.setExpert()
            self.save.setExpert()
            self.unfreeze.setExpert()
            self.start.setExpert()
            self.stop.setExpert()


class CountsFrame(tk.LabelFrame):
    """
    Frame for count rate estimates
    """
    def __init__(self, master):
        """
        master : enclosing widget
        """
        tk.LabelFrame.__init__(
            self, master, pady=2, text='Count & S-to-N estimator')

        # divide into left and right frames
        lframe = tk.Frame(self, padx=2)
        rframe = tk.Frame(self, padx=2)

        # entries
        self.filter    = drvs.Radio(
            lframe, ('u', 'g', 'r', 'i', 'z'), 3, self.checkUpdate, initial=1)
        self.mag       = drvs.RangedFloat(
            lframe, 18., 0., 30., self.checkUpdate, True, width=5)
        self.seeing    = drvs.RangedFloat(
            lframe, 1.0, 0.2, 20., self.checkUpdate, True, True, width=5)
        self.airmass   = drvs.RangedFloat(
            lframe, 1.5, 1.0, 5.0, self.checkUpdate, True, width=5)
        self.moon      = drvs.Radio(lframe, ('d', 'g', 'b'),  3, self.checkUpdate)

        # results
        self.cadence   = drvs.Ilabel(rframe,text='UNDEF',width=10,anchor=tk.W)
        self.exposure  = drvs.Ilabel(rframe,text='UNDEF',width=10,anchor=tk.W)
        self.duty      = drvs.Ilabel(rframe,text='UNDEF',width=10,anchor=tk.W)
        self.peak      = drvs.Ilabel(rframe,text='UNDEF',width=10,anchor=tk.W)
        self.total     = drvs.Ilabel(rframe,text='UNDEF',width=10,anchor=tk.W)
        self.ston      = drvs.Ilabel(rframe,text='UNDEF',width=10,anchor=tk.W)
        self.ston3     = drvs.Ilabel(rframe,text='UNDEF',width=10,anchor=tk.W)

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
        tk.Label(rframe,text='Cadence:').grid(
            row=0,column=0,padx=5,pady=3,sticky=tk.W)
        self.cadence.grid(row=0,column=1,padx=5,pady=3,sticky=tk.W)

        tk.Label(rframe,text='Exposure:').grid(
            row=1,column=0,padx=5,pady=3,sticky=tk.W)
        self.exposure.grid(row=1,column=1,padx=5,pady=3,sticky=tk.W)

        tk.Label(rframe,text='Duty cycle:').grid(
            row=2,column=0,padx=5,pady=3,sticky=tk.W)
        self.duty.grid(row=2,column=1,padx=5,pady=3,sticky=tk.W)

        tk.Label(rframe,text='Peak:').grid(
            row=3,column=0,padx=5,pady=3,sticky=tk.W)
        self.peak.grid(row=3,column=1,padx=5,pady=3,sticky=tk.W)

        tk.Label(rframe,text='Total:').grid(
            row=4,column=0,padx=5,pady=3,sticky=tk.W)
        self.total.grid(row=4,column=1,padx=5,pady=3,sticky=tk.W)

        tk.Label(rframe,text='S/N:').grid(
            row=5,column=0,padx=5,pady=3,sticky=tk.W)
        self.ston.grid(row=5,column=1,padx=5,pady=3,sticky=tk.W)

        tk.Label(rframe,text='S/N (3h):').grid(
            row=6,column=0,padx=5,pady=3,sticky=tk.W)
        self.ston3.grid(row=6,column=1,padx=5,pady=3,sticky=tk.W)

        # slot frames in
        lframe.grid(row=0,column=0,sticky=tk.W+tk.N)
        rframe.grid(row=0,column=1,sticky=tk.W+tk.N)

    def checkUpdate(self, *args):
        """
        Updates values after first checking instrument parameters are OK.
        This is not integrated within update to prevent ifinite recursion
        since update gets called from ipars.
        """

        if not self.check():
            g.clog.warn('Current observing parameters are not valid.')
            return False

        if not g.ipars.check():
            g.clog.warn('Current instrument parameters are not valid.')
            return False

    def check(self):
        """
        Checks values
        """
        status = True

        if self.mag.ok():
            self.mag.config(bg=g.COL['main'])
        else:
            self.mag.config(bg=g.COL['warn'])
            status = False

        if self.airmass.ok():
            self.airmass.config(bg=g.COL['main'])
        else:
            self.airmass.config(bg=g.COL['warn'])
            status = False

        if self.seeing.ok():
            self.seeing.config(bg=g.COL['main'])
        else:
            self.seeing.config(bg=g.COL['warn'])
            status = False

        return status

    def update(self, *args):
        """
        Updates values. You should run a check on the instrument and
        target parameters before calling this.
        """

        expTime, deadTime, cycleTime, dutyCycle, frameRate = g.ipars.timing()

        total, peak, peakSat, peakWarn, ston, ston3 = \
            self.counts(expTime, cycleTime)

        if cycleTime < 0.01:
            self.cadence.config(text='{0:7.5f} s'.format(cycleTime))
        elif cycleTime < 0.1:
            self.cadence.config(text='{0:6.4f} s'.format(cycleTime))
        elif cycleTime < 1.:
            self.cadence.config(text='{0:5.3f} s'.format(cycleTime))
        elif cycleTime < 10.:
            self.cadence.config(text='{0:4.2f} s'.format(cycleTime))
        elif cycleTime < 100.:
            self.cadence.config(text='{0:4.1f} s'.format(cycleTime))
        elif cycleTime < 1000.:
            self.cadence.config(text='{0:4.0f} s'.format(cycleTime))
        else:
            self.cadence.config(text='{0:5.0f} s'.format(cycleTime))

        if expTime < 0.01:
            self.exposure.config(text='{0:7.5f} s'.format(expTime))
        elif expTime < 0.1:
            self.exposure.config(text='{0:6.4f} s'.format(expTime))
        elif expTime < 1.:
            self.exposure.config(text='{0:5.3f} s'.format(expTime))
        elif expTime < 10.:
            self.exposure.config(text='{0:4.2f} s'.format(expTime))
        elif expTime < 100.:
            self.exposure.config(text='{0:4.1f} s'.format(expTime))
        elif expTime < 1000.:
            self.exposure.config(text='{0:4.0f} s'.format(expTime))
        else:
            self.exposure.config(text='{0:5.0f} s'.format(expTime))

        self.duty.config(text='{0:4.1f} %'.format(dutyCycle))
        self.peak.config(text='{0:d} cts'.format(int(round(peak))))
        if peakSat:
            self.peak.config(bg=g.COL['error'])
        elif peakWarn:
            self.peak.config(bg=g.COL['warn'])
        else:
            self.peak.config(bg=g.COL['main'])

        self.total.config(text='{0:d} cts'.format(int(round(total))))
        self.ston.config(text='{0:.1f}'.format(ston))
        self.ston3.config(text='{0:.1f}'.format(ston3))

    def counts(self, expTime, cycleTime, ap_scale=1.6, ndiv=5):
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

        # avalanche mode y/n?
        lnormal = not g.ipars.avalanche()

        # Set the readout speed
        readSpeed = g.ipars.readSpeed.value()

        if readSpeed == 'Fast':
            video = VIDEO_NORM_FAST if lnormal else VIDEO_AV_FAST
        elif readSpeed == 'Medium':
            video = VIDEO_NORM_MED if lnormal else VIDEO_AV_MED
        elif readSpeed == 'Slow':
            video = VIDEO_NORM_SLOW if lnormal else VIDEO_AV_SLOW
        else:
            raise drvs.DriverError(
                'drivers.CountsFrame.counts: readout speed = '
                + readSpeed + ' not recognised.')

        if g.ipars.app == 'Windows':
            xbin, ybin = g.ipars.wframe.xbin.value(), g.ipars.wframe.ybin.value()
        else:
            xbin, ybin = g.ipars.pframe.xbin.value(), g.ipars.pframe.ybin.value()

        # calculate SN info.
        zero, sky, skyTot, gain, read, darkTot = 0., 0., 0., 0., 0., 0.
        total, peak, correct, signal, readTot, seeing = 0., 0., 0., 0., 0., 0.
        noise,  skyPerPixel, narcsec, npix, signalToNoise3 = 1., 0., 0., 0., 0.

        tinfo   = g.TINS[g.cpars['telins_name']]
        filtnam = self.filter.value()

        zero    = tinfo['zerop'][filtnam]
        mag     = self.mag.value()
        seeing  = self.seeing.value()
        sky     = g.SKY[self.moon.value()][filtnam]
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
        total   = 10.**((zero-mag-airmass*g.EXTINCTION[filtnam])/2.5)*expTime

        # compute fraction that fall in central pixel
        # assuming target exactly at its centre. Do this
        # by splitting each pixel of the central (potentially
        # binned) pixel into ndiv * ndiv points at
        # which the seeing profile is added. sigma is the
        # RMS seeing in terms of pixels.
        sigma = seeing/g.EFAC/plateScale

        sum = 0.
        for iyp in range(ybin):
            yoff = -ybin/2.+iyp
            for ixp in range(xbin):
                xoff = -xbin/2.+ixp
                for iys in range(ndiv):
                    y = (yoff + (iys+0.5)/ndiv)/sigma
                    for ixs in range(ndiv):
                        x = (xoff + (ixs+0.5)/ndiv)/sigma
                        sum += math.exp(-(x*x+y*y)/2.)
        peak = total*sum/(2.*math.pi*sigma**2*ndiv**2)

#        peak    = total*xbin*ybin*(plateScale/(seeing/EFAC))**2/(2.*math.pi)

        # Work out fraction of flux in aperture with radius AP_SCALE*seeing
        correct = 1. - math.exp(-(g.EFAC*ap_scale)**2/2.)

        # expected sky e- per arcsec
        skyPerArcsec = 10.**((zero-sky)/2.5)*expTime
        skyPerPixel  = skyPerArcsec*plateScale**2*xbin*ybin
        narcsec      = math.pi*(ap_scale*seeing)**2
        skyTot       = skyPerArcsec*narcsec
        npix         = math.pi*(ap_scale*seeing/plateScale)**2/xbin/ybin

        signal       = correct*total # in electrons
        darkTot      = npix*DARK_E*expTime  # in electrons
        readTot      = npix*read**2 # in electrons
        cic          = 0 if lnormal else CIC

        # noise, in electrons
        if lnormal:
            noise = math.sqrt(readTot + darkTot + skyTot + signal + cic)
        else:
            # assume high gain observations in proportional mode
            noise = math.sqrt(readTot/AVALANCHE_GAIN_9**2 +
                           2.0*(darkTot + skyTot + signal) + cic)

        # Now compute signal-to-noise in 3 hour seconds run
        signalToNoise3 = signal/noise*math.sqrt(3*3600./cycleTime);

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

class UspecError(Exception):
    pass
