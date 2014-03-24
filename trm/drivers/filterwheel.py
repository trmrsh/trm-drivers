#!/usr/bin/env python

"""
Classes for accessing the ultraspec filter wheel.

Two main classes::

 FilterWheel : provides an API to control the wheel. This class once created
            gives an interface to the wheel.

 WheelController : creates a window with buttons which use the FilterWheel
"""
import Tkinter as tk
import serial

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
        self.ser = serial.Serial(self.port,baudrate=self.baudrate,
                                 timeout=self.default_timeout)
        self.connected = True

    def init(self):
        """
        enables serial mode on the filter wheel. this
        should always be the first command run after
        connecting to the wheel
        """
        response = self.sendCommand('WSMODE')
        if response != "!":
            raise FilterWheelError('Could not initialise wheel for' + \
                                       ' serial commands')
        self.initialised = True

    def sendCommand(self,comm):
        """
        wrapper function to send commands to filter wheel
        """
        if not self.initialised and comm != 'WSMODE':
            raise FilterWheelError('Filter wheel not initialised')

        if not self.connected:
            raise FilterWheelError('Filter wheel not connected')

        if comm == 'WHOME' or comm.startswith('WGOTO'):
            self.ser.setTimeout(30)
        else:
            self.ser.setTimeout(self.default_timeout)
        self.ser.write(comm+'\r\n',)
        retVal = self.ser.readline()

        # return command with leading and trailing whitespace removed
        return retVal.strip()

    def close(self):
        """
        disables serial mode and disconnects from serial port
        """
        # disable serial mode operation for the serial port
        self.sendCommand('WEXITS')
        self.ser.close()
        self.connected   = False
        self.initialised = False

    def home(self):
        """
        sends a home command to the wheel. this shouldn't be
        needed very often, only if the slide has got into a
        confused state
        """
        response = self.sendCommand('WHOME')
        if response == 'ER=3':
            raise FilterWheelError('Could not ID filter wheel after HOME')
        elif response == 'ER=1':
            raise FilterWheelError('Filter wheel homing took too many steps')

    def getID(self):
        """
        returns ID of filter wheel, and checks for valid response
        """
        response = self.sendCommand('WIDENT').strip()
        validIDs = ['A','B','C','D','E']
        if not response in validIDs:
            raise FilterWheelError('Bad filter wheel ID\n'+response)
        return response

    def getPos(self):
        """
        gets current position of wheel (from 1 to 6)
        """
        response = self.sendCommand('WFILTR')
        filtNum = int(response)
        return filtNum

    def getNames(self):
        """
        returns the possible names. should always be 123456
        """
        response = self.sendCommand("WREAD")
        return response.split()

    def goto(self,position):
        """
        moves to desired position. positions 1 thru 6 are valid
        """
        if position > 6 or position < 1:
            raise FilterWheelError('Invalid filter wheel position')
        response = self.sendCommand('WGOTO'+repr(position))
        if response == 'ER=4':
            raise FilterWheelError('filter wheel is stuck')
        if response == 'ER=5':
            raise FilterWheelError('requested position (' +
                                   position + ') not valid')
        if response == 'ER=6':
            raise FilterWheelError('filter wheel is slipping')

        if response != '*':
            raise FilterWheelError('unrecognised error ' + response)

    def reboot(self):
        """
        use this to fix a non-responding filter wheel
        """
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

        # Try to connect to the wheel. Raises an Exception
        # if no wheel available
        if not wheel.connected:
            wheel.connect()
            wheel.init()

        width = 12
        tk.Toplevel.__init__(self)
        self.title('Filter selector')
        self.wheel = wheel

        # current index
        findex = wheel.getPos()-1

        toplab = tk.Label(self,text='Current filter: ', justify=tk.RIGHT)
        toplab.grid(row=0,column=0)

        self.current = drvs.Ilabel(self,
                                   text=g.cpars['active_filter_names'][findex],
                                   justify=tk.LEFT)
        self.current.grid(row=0,column=1)

        self.filter = drvs.Choice(self, g.cpars['active_filter_names'],
                                  initial=g.cpars['active_filter_names'][findex],
                                  width=width-1)
        self.filter.grid(row=1,column=0)

        self.go     = drvs.ActButton(self, width, self._go, text='go')
        self.go.grid(row=1, column=1)

        self.home   = drvs.ActButton(self, width, self._home, text='home wheel')
        self.home.grid(row=2, column=0)

        self.init   = drvs.ActButton(self, width, self._init, text='init wheel')
        self.init.grid(row=2, column=1)

        # override the 'x' to kill the window
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _go(self, *args):
        findex = self.filter.options.index(self.filter.value())+1
        g.clog.log.info('Moving to filter position = ' + str(findex) + '\n')
        self.wheel.goto(findex)
        self.current.configure(text=g.cpars['active_filter_names'][findex-1])
        g.clog.log.info('Filter moved successfully\n')

    def _home(self, *args):
        g.clog.log.info('Homing filter wheel ...\n')
        self.wheel.home()
        self.current.configure(text=g.cpars['active_filter_names'][0])
        g.clog.log.info('Filter homed\n')

    def _init(self, *args):
        g.clog.log.info('Initialising filter wheel ...\n')
        self.wheel.reboot()
        self.current.configure(text=g.cpars['active_filter_names'][0])
        g.clog.log.info('Filter wheel initialised\n')

    def _close(self, *args):
        """
        Closes the wheel, and deletes the window
        """
        self.wheel.close()
        g.clog.log.info('Filter closed\n')
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

        tk.Label(self,text='Old filter name:').grid(row=0,column=0)
        self.old = drvs.Choice(self, g.cpars['active_filter_names'], width=12)
        self.old.grid(row=0,column=1,padx=2,pady=2)

        tk.Label(self,text='New filter name:').grid(row=1,column=0)
        self.new  = drvs.Choice(self, g.cpars['filter_names'], width=12)
        self.new.grid(row=1, column=1,padx=2,pady=2)

        self.confirm = drvs.ActButton(self, 22, self._make_change,
                                      text='Confirm filter change')
        self.confirm.grid(row=2, column=0, columnspan=2, pady=2)

    def _make_change(self, *args):
        indx    = self.old.getIndex()
        ofilter = self.old.value()
        nfilter = self.new.value()
        g.cpars['active_filter_names'][indx] = nfilter

        # reconfig the filters in RunPars
        g.rpars.filter.buttons[indx].config(text=nfilter)

        # reconfig the old filter choices
        m = self.old.children['menu']
        m.entryconfig(indx, label=nfilter)
        self.old.set(nfilter)

        # report back
        g.clog.log.info('Filter name changed: ' + ofilter + ' ---> ' + nfilter + '\n')
        g.clog.log.warn('You need to physically change the filter as well!')

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

