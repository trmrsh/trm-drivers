#!/usr/bin/env python

"""
Classes for accessing the ultraspec filter wheel.

Two main classes::

 FilterWheel : provides an API to control the wheel. This class once created
            gives an interface to the wheel.

 WheelController : creates a window with buttons which use the FilterWheel
"""
import Tkinter as tk
import tkMessageBox
import serial, time

import globals as g
import drivers as drvs

class FilterWheel(object):
    """
    Class to control the ULTRASPEC filterwheel.
    """

    def __init__(self,port='/dev/filterwheel', default_timeout=2):
        """
        initialise filter wheel object. doesnt actually connect
        """
        self.port = '/dev/filterwheel'
        self.baudrate = 19200
        self.default_timeout = default_timeout
        self.connected   = False
        self.initialised = False

    def connect(self):
        """
        Connects to the serial port of the filter wheel
        """
        g.clog.debug('Filterwheel: connecting to serial port')
        self.ser = serial.Serial(self.port,baudrate=self.baudrate,
                                 timeout=self.default_timeout)
        self.connected = True
        g.clog.debug('Filterwheel: connected to serial port')

    def init(self):
        """
        enables serial mode on the filter wheel. this
        should always be the first command run after
        connecting to the wheel
        """
        g.clog.debug('Filterwheel: initialising')

        response = self.sendCommand('WSMODE')
        if response != "!":
            g.clog.debug('First attempt at initialising failed; trying again')
            # wait a bit, try once more
            time.sleep(2)
            response = self.sendCommand('WSMODE')
            if response != "!":
                raise FilterWheelError('Could not initialise wheel for' +
                                       ' serial commands')
        self.initialised = True
        g.clog.debug('Filterwheel: serial mode enabled (WSMODE)')

    def sendCommand(self,comm):
        """
        wrapper function to send commands to filter wheel
        """

        if not self.connected:
            raise FilterWheelError('Filter wheel not connected')

        if not self.initialised and comm != 'WSMODE':
            raise FilterWheelError('Filter wheel not initialised')

        if comm == 'WHOME' or comm.startswith('WGOTO'):
            g.clog.debug('Filterwheel: setting timeout to 30 secs')
            self.ser.setTimeout(30)
        else:
            g.clog.debug('Filterwheel: setting timeout to ' +
                         str(self.default_timeout) + ' secs')
            self.ser.setTimeout(self.default_timeout)

        g.clog.debug('Filterwheel: sending command = ' + comm)
        self.ser.write(comm+'\r\n',)
        retVal = self.ser.readline()
        g.clog.debug('Filterwheel: received = ' + retVal.strip())

        # return command with leading and trailing whitespace removed
        return retVal.strip()

    def close(self):
        """
        disables serial mode and disconnects from serial port
        note this could throw
        """
        # disable serial mode operation for the serial port
        g.clog.debug('Filterwheel: closing serial port')
        if self.initialised:
            self.sendCommand('WEXITS')
            self.initialised = False

        if self.connected:
            self.ser.close()
            self.connected = False

        g.clog.debug('Filterwheel: closed serial port')


    def home(self):
        """
        sends a home command to the wheel. this shouldn't be
        needed very often, only if the slide has got into a
        confused state
        """
        g.clog.debug('Filterwheel: homing the wheel')
        response = self.sendCommand('WHOME')
        if response == 'ER=1':
            raise FilterWheelError('Filter wheel homing took too many steps')
        elif response == 'ER=3':
            raise FilterWheelError('Could not ID filter wheel after HOME')
        elif response == 'ER=6':
            raise FilterWheelError('Filter wheel is slipping')
        g.clog.debug('Filterwheel: home returned ' + response)

    def getID(self):
        """
        returns ID of filter wheel, and checks for valid response
        """
        g.clog.debug('Filterwheel: getting ID')
        response = self.sendCommand('WIDENT').strip()
        validIDs = ['A','B','C','D','E']
        if not response in validIDs:
            raise FilterWheelError('Bad filter wheel ID\n'+response.strip())
        return response

    def getPos(self):
        """
        gets current position of wheel (from 1 to 6)
        """
        g.clog.debug('Filterwheel: getting position')
        response = self.sendCommand('WFILTR')
        g.clog.debug('Poisition response = ' + response.strip())
        filtNum = int(response)
        return filtNum

    def getNames(self):
        """
        returns the possible names. should always be 123456
        """
        g.clog.debug('Filterwheel: getting names')
        response = self.sendCommand("WREAD")
        g.clog.debug('Names = ' + response.strip())
        return response.split()

    def goto(self,position):
        """
        moves to desired position. positions 1 thru 6 are valid
        """
        g.clog.debug('Filterwheel: changing to position ' +
                     str(position))

        if position > 6 or position < 1:
            raise FilterWheelError('Invalid filter wheel position')

        response = self.sendCommand('WGOTO'+repr(position))

        if response == 'ER=4':
            raise FilterWheelError('filter wheel is stuck')
        elif response == 'ER=5':
            raise FilterWheelError('requested position (' +
                                   position + ') not valid')
        elif response == 'ER=6':
            raise FilterWheelError('filter wheel is slipping')
        elif response != '*':
            raise FilterWheelError('unrecognised error = [' +
                                   response.strip() + ']')

    def reboot(self):
        """
        use this to fix a non-responding filter wheel
        """
        g.clog.debug('Filterwheel: rebooting')
        self.close()
        time.sleep(2)
        self.connect()
        self.init()
        self.home()

class WheelController(tk.Toplevel):
    """
    Class to allow control of the filter wheel. Opens in
    a new window.
    """

    def __init__(self, wheel):
        """
        wheel   : a FilterWheel instance representing the wheel
        """

        width = 12
        tk.Toplevel.__init__(self, padx=8, pady=8)
        self.title('Filter selector')
        self.wheel = wheel

        toplab = tk.Label(self,text='Current filter: ')
        toplab.grid(row=0,column=0,pady=3)

        # current index
        try:
            # Try to connect to the wheel. Raises an Exception
            # if no wheel available
            if not self.wheel.connected:
                self.wheel.connect()
                self.wheel.init()

            findex = self.wheel.getPos()-1

            self.current = drvs.Ilabel(
                self,text=g.cpars['active_filter_names'][findex])

        except Exception, err:
            g.clog.warn('Failed to get current filter position.\n')
            g.clog.warn('Error: ' + str(err) + '\n')
            self.current = drvs.Ilabel(self,text='UNKNOWN')
            findex = 0

        self.current.grid(row=0,column=1, sticky=tk.W, pady=3)

        self.filter = drvs.Choice(
            self, g.cpars['active_filter_names'],
            initial=g.cpars['active_filter_names'][findex],
            width=width-1)
        self.filter.grid(row=1,column=0)

        self.go = drvs.ActButton(self, width, self._go, text='go')
        self.go.grid(row=1, column=1)

        self.home = drvs.ActButton(self, width, self._home, text='home wheel')
        self.home.grid(row=2, column=0)

        self.init = drvs.ActButton(self, width, self._init, text='init wheel')
        self.init.grid(row=2, column=1)

        # override the 'x' to kill the window
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _go(self, *args):
        if drvs.isRunActive():
            tkMessageBox.showwarning(
                'Run active',
                'Sorry; you cannot change filters during a run.')
            return

        try:
            if not self.wheel.connected:
                self.wheel.connect()
                self.wheel.init()
            findex = self.filter.options.index(self.filter.value())+1
            g.clog.info('Moving to filter position = ' + str(findex) +
                        ', name = ' + g.cpars['active_filter_names'][findex-1])
            self.wheel.goto(findex)
            self.current.configure(
                text=g.cpars['active_filter_names'][findex-1])
            g.clog.info('Filter moved successfully')
        except Exception, err:
            g.clog.warn('Filter change failed.')
            g.clog.warn('Error: ' + str(err))
            g.clog.warn('You might want to try an "init".')

    def _home(self, *args):
        g.clog.info('Homing filter wheel ...')
        try:
            if not self.wheel.connected:
                self.wheel.connect()
                self.wheel.init()
            self.wheel.home()
            self.current.configure(text=g.cpars['active_filter_names'][0])
            g.clog.info('Filter homed\n')
        except Exception, err:
            g.clog.warn('Could not home wheel.')
            g.clog.warn('Error: ' + str(err))
            g.clog.warn('You might want to try an "init".')

    def _init(self, *args):
        g.clog.info('Initialising filter wheel ...')
        try:
            self.wheel.reboot()
            self.current.configure(text=g.cpars['active_filter_names'][0])
            g.clog.info('Filter wheel initialised')
        except Exception, err:
            g.clog.warn('Could not initialise wheel.')
            g.clog.warn('Error: ' + str(err))
            g.clog.warn('You might want to try again once or twice, or stop & restart usdriver, or perhaps the wheel needs adjusting. See the online ultraspec manual.')

    def _close(self, *args):
        """
        Closes the wheel, and deletes the window
        """
        try:
            self.wheel.close()
            g.clog.info('Filter wheel closed')
        except Exception, err:
            g.clog.warn('Problem closing wheel.')
            g.clog.warn('Error: ' + str(err))
        self.destroy()


class FilterEditor(tk.Toplevel):
    """
    Class to allow editing of the active filters. The list of *possible*
    filters is set in the configuration file and any changes to the
    available set must be edited directly there.
    """

    def __init__(self):

        tk.Toplevel.__init__(self)
        self.title('Filter editor')

        tk.Label(self,text='Pos.').grid(row=0,column=0)
        tk.Label(self,text='Filter').grid(row=0,column=1)

        self.fnames = []
        row = 1
        for i, fname in enumerate(g.cpars['active_filter_names']):
            tk.Label(self,text=str(i+1)).grid(row=row,column=0)
            self.fnames.append(
                drvs.Choice(self, g.cpars['filter_names'], fname, width=12))
            self.fnames[-1].grid(row=row,column=1)
            row += 1

        self.confirm = drvs.ActButton(self, 22, self._make_change,
                                      text='Confirm filter change')
        self.confirm.grid(row=row, column=0, columnspan=2, pady=2)

    def _make_change(self, *args):
        """
        Implements new choices
        """
        nchange = 0
        for i, choice in enumerate(self.fnames):
            nfilter = choice.value()
            ofilter = g.cpars['active_filter_names'][i]

            if nfilter != ofilter:

                # update active filter names
                g.cpars['active_filter_names'][i] = nfilter

                # reconfig the filters in RunPars
                g.rpars.filter.buttons[i].config(text=nfilter)
                g.rpars.filter.buttons[i].config(value=nfilter)

                # report changes
                g.clog.info('Filter change: ' + ofilter + ' ---> ' + \
                            nfilter + '\n')

                nchange += 1
        if nchange:
            g.clog.warn('You must physically change the filter(s) as well!\n')

class FilterWheelError(Exception):
    pass

if __name__ == "__main__":

    wheel = FilterWheel()
    try:
        wheel.connect()
        wheel.init()
        print 'Started'
        print 'Currently in filter position ', wheel.getPos()
        print 'This is filter wheel ', wheel.getID()
        print 'Available positions: ', wheel.getNames()
        print "GOTO 3"
        wheel.goto(3)
        print "HOME"
        wheel.home()
        print 'Disconnecting'
        wheel.close()
        print 'Finished normally'
    except:
        wheel.close()
        print 'Finished badly'

