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
import drivers as drvs

class FilterWheel(object):

    def __init__(self,port='/dev/filterwheel',default_timeout=2):
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

    def sendCommand(self,str):
        """
        wrapper function to send commands to filter wheel
        """
        if not self.initialised:
            raise FilterWheelError('Filter wheel not initialised')

        if not self.connected:
            raise FilterWheelError('Filter wheel not connected')

        if str=='WHOME' or str.startswith('WGOTO'):
            self.ser.setTimeout(30)
        else:
            self.ser.setTimeout(self.default_timeout)
        self.ser.write(str+'\r\n',)
        retVal = self.ser.readline()

        # return command with leading and trailing whitespace removed
        return retVal.lstrip().rstrip()

    def close(self):
        """
        disables serial mode and disconnects from serial port
        """
        # disable serial mode operation for the serial port
        self.sendCommand('WEXITS')
        self.ser.close()
        self.connected = False
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

    def reBoot(self):
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

    def __init__(self, wheel, share):
        """
        wheel   : a FilterWheel instance representing the wheel

        share   : dictionary of other objects. Must have 'cpars' the
                          configuration parameters, 'instpars' the instrument
                  setup parameters (windows etc), and 'runpars' the
                  run parameters (target name etc), 'clog' and 'rlog'
        """

        width = 10
        tk.Toplevel.__init__(self)
        self.title('Filter selector')

        cpars, clog = share['cpars'], share['clog']
        try:
            if not wheel.connected:
                wheel.connect()
                wheel.init()
        except Exception, err:
            clog.log.warn('Filter wheel error\n')
            clog.log.warn(str(err) + '\n')

        self.filter = drvs.Choice(self, cpars['active_filter_names'],
                                  width=width)
        self.filter.grid(row=0,column=0)

        self.go     = drvs.ActButton(self, width, share, self._go, text='go')
        self.go.grid(row=0, column=1)

        self.home   = drvs.ActButton(self, width, share, text='home')
        self.home.grid(row=1, column=0)

        self.init   = drvs.ActButton(self, width, share, text='init')
        self.init.grid(row=1, column=1)

        self.close   = drvs.ActButton(self, width, share, text='close')
        self.close.grid(row=2, column=1)

        self.wheel = wheel
        self.share = share

    def _go(self, *args):
        """
        Defines go action. Might want to do this in background.
        """
        findex = self.filter.options.index(self.filter.value())+1
        print('filter index desired =',findex)
        self.wheel.goto(findex)

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

