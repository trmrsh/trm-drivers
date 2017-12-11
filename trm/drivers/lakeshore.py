import serial, os

# error class for lakeshore
class LakeshoreError(Exception):
    pass

# Lakshore device serial interface
class Lakeshore(object):
    '''python class to communicate with the lakeshore temperature controller'''
    def __init__(self, port='/dev/ttyS0'):
        # create serial port object with timeout of 2 secs
        self.com = serial.Serial(
            port, 9600, serial.SEVENBITS,
            serial.PARITY_ODD, serial.STOPBITS_ONE, 2, 0, 0
        )
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
        self.com.write(tmp.encode())

        # get response
        rep = self.com.readline().decode()

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
            e = LakeshoreError('Cannot get temperature from lakeshore')
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


class LakeFile(object):
    """
    Class to get temperature infor from Lakeshore log file to avoid
    interacting via serial port
    """

    DDIR = '/home/observer/Lakeshore/'

    def __init__(self):
        """
        Try to read a log file to see whether there is one
        """
        self.temps()

    def temps(self):
        """
        Get temperatures and heater percentage from log file in one go
        """

        # find log files
        fnames = [os.path.join(LakeFile.DDIR, fname)
                  for fname in os.listdir(LakeFile.DDIR) \
                  if fname.startswith('Lakeshore_log') > -1]
        if len(fnames) == 0:
            raise LakeshoreError('Failed to find any Lakeshore log files in ' + LakeFile.DDIR)

        # find most recently modified file
        mtime_max = os.stat(fnames[0]).st_mtime
        fname_max = fnames[0]
        for fname in fnames[1:]:
            mtime = os.stat(fname).st_mtime
            if mtime > mtime_max:
                mtime_max = mtime
                fname_max = fname

        # open it and read the last line
        with open(fname_max) as fin:
            for line in fin:
                last = line

        elems = last.split(',')

        tempa  = float(elems[5])
        tempb  = float(elems[6])
        heater = float(elems[7])
        return (tempa,tempb,heater)
