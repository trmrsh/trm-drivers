import serial

# error class for lakeshore
class LakeshoreError(Exception):
    pass
    
# Lakshore device serial interface
class Lakeshore(object):
    '''python class to communicate with the lakeshore temperature controller'''
    def __init__(self, port='/dev/ttyS0'):
        # create serial port object with timeout of 2 secs
        self.com = serial.Serial(port, 9600, serial.SEVENBITS, serial.PARITY_ODD, serial.STOPBITS_ONE, 2, 0, 0)
        if not self.com.isOpen():
            self.com.open()
        self.com.flushInput()
        self.com.flushOutput()
        self.com.close()

    def shutDown(self):
        try:
            if self.com.isOpen():
                self.com.close()
        except:
            raise LakeshoreError('Could not close down connection')
        
    def _cmd(self, cmd):
        '''sends a command to the lakeshore and returns the response'''
        tmp = cmd + '\r\n'

        # open if need to (should need to as it's a bad idea to leave open permanently)
        if not self.com.isOpen():
            self.com.open()

        # flush IO buffers
        self.com.flushInput()
        self.com.flushOutput()

        # send command to lakeshore
        self.com.write(tmp)
        # get response
        rep = self.com.readline()

        #close down
        if self.com.isOpen():
            self.com.close()
        # strip leading and trailing whitespace from response and return
        return rep.lstrip().rstrip()
    
    def tempa(self):
        '''gets the A temperature probe value (this should be the chip temp)'''
        try:
            val = self._cmd('KRDG? A')
            #strip off sign
            val = val[1:]
            return float(val)
        except:
            e = LakeshoreError('Cannot get temp from lakeshore')
            raise e

    def tempb(self):
        '''gets the B temperature probe value (this should be the cold finger temp)'''
        try:
            val = self._cmd('KRDG? B')
            #strip off sign
            val = val[1:]
            return float(val)
        except:
            e = LakeshoreError('Cannot get temp from lakeshore')
            raise e

    def heater(self):
        '''gets the heater power, in percent'''    
        try:
            val = self._cmd('HTR? ')
            #strip off sign
            val = val[1:]
            return float(val)
        except:
            e = LakeshoreError('Cannot get heater power from lakeshore')
            raise e


