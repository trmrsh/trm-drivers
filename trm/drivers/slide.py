"""
Class to talk to the focal plane slide

Written by Stu.
"""

from __future__ import print_function
import serial
import struct

class SlideError(Exception):
    pass

# number of bytes to transmit & recieve
PACKET_SIZE = 6

# command numbers
RESET            = 0
HOME             = 1
MOVE_ABSOLUTE    = 20
MOVE_RELATIVE    = 21
STOP             = 23
RESTORE          = 36
SET_MODE         = 40
RETURN_SETTING   = 53
POSITION         = 60
NULL             = 0

# error return from slide
ERROR            = 255

# unit number, may depend upon how device is connected to the port
UNIT             = 1

PERIPHERAL_ID    = 0
POTENTIOM_OFF    = 8
POTENTIOM_ON     = 0
    
TRUE             = 1
FALSE            = 0

# the next define ranges for the movement in terms of 
#microsteps, millimetres and pixels
MIN_MS           = 0
MAX_MS           = 672255
MM_PER_MS        = 0.00015619
MIN_MM           = MM_PER_MS*MIN_MS
MAX_MM           = MM_PER_MS*MAX_MS

# these set the limits in pixel numbers. They are telescope dependent
MIN_PX           = 1230.0
MAX_PX           = -798.
PARK_POS         = 1100.

# the slide starts moving taking time MAX_STEP_TIME and accelerates to
# MIN_STEP_TIME (in seconds/steps) at a rate of STEP_TIME_ACCN
# (secs/step/step) These parameters are used to estimate the time taken to
# make a move along with the number of microsteps/step
MAX_STEP_TIME    = 0.0048
MIN_STEP_TIME    = 0.0025
STEP_TIME_ACCN   = 0.00005
MS_PER_STEP      = 64

# MAX_TIMEOUT is set by the time taken to move the slide from one end to the
# other MIN_TIMEOUT is used as a lower limt on all timeouts (seconds)
MIN_TIMEOUT      = 2
MAX_TIMEOUT      = 70

class Slide(object):
    
    def __init__(self,port='/dev/slide'):
        self.port = port
        self.default_timeout = MIN_TIMEOUT
        self.connected = False

    def _open_port(self):
        try:
            self.ser = serial.Serial(self.port,baudrate=9600)
            self.connected=True
        except:
            self.connected=False

    def _close_port(self):
        try:
            self.ser.close()
            self.connected = False
        except Exception as e:
            raise SlideError(e)

    def _sendByteArr(self,byteArr,timeout):
        if self.connected:
            self.ser.timeout = timeout
            bytes_sent = self.ser.write(byteArr)
            if bytes_sent != 6:
                raise SlideError('did not send 6 bytes to slide')
        else:
            raise SlideError('cannot send bytes to an unconnected slide')
    
    def _readBytes(self,timeout):
        if self.connected:
            self.ser.timeout = timeout
            bytes = self.ser.read(6)
            byteArr = bytearray(bytes)
            if len(byteArr) != 6:
                raise SlideError('did not get 6 bytes back from slide')
            return byteArr
        else:
            raise SlideError('cannot send bytes to an unconnected slide')

    def _decodeCommandData(self,byteArr):
        return struct.unpack('<L',byteArr[2:])[0]

    def _encodeCommandData(self,int):
        return bytearray(struct.pack('<L',int))

    def _encodeByteArr(self,intArr):
        if len(intArr) != 6:
            raise SlideError('must send 6 bytes to slide: cannot send ' + 
                             repr(intArr))
        return bytearray(intArr)

    def _compute_timeout(self,nmicrostep):
        nstep = abs(nmicrostep)/MS_PER_STEP
        nacc  = (MAX_STEP_TIME - MIN_STEP_TIME)/STEP_TIME_ACCN
        if nacc > nstep:
            time_estimate = (MAX_STEP_TIME - STEP_TIME_ACCN * nstep/2)*nstep
        else:
            time_estimate = (MAX_STEP_TIME + MIN_STEP_TIME)*nacc/2 + \
                MIN_STEP_TIME*(nstep-nacc)
        if time_estimate > 5:
            print('Rough estimate of time to perform command = %d seconds' 
                  % int(time_estimate))

        timeout = time_estimate+2
        timeout = timeout if timeout > MIN_TIMEOUT else MIN_TIMEOUT
        timeout = timeout if timeout < MAX_TIMEOUT else MAX_TIMEOUT
        return timeout
        
    def _getPosition(self):
        """
        returns current position of the slide in microsteps
        """
        if not self._hasBeenHomed():
            raise SlideError('position of slide is undefined until slide homed')
        if not self.connected:
            self._open_port()
        byteArr = self._encodeByteArr([UNIT,POSITION,NULL,NULL,NULL,NULL])
        self._sendByteArr(byteArr,self.default_timeout)
        byteArr = self._readBytes(timeout=self.default_timeout)
        self._close_port()
        pos = self._decodeCommandData(byteArr)
        return pos
        
    def _hasBeenHomed(self):
        """
        returns true if the slide has been homed and has a calibrated
        position
        """
        if not self.connected:
            self._open_port()
        byteArr = self._encodeByteArr([UNIT,RETURN_SETTING,
                                       SET_MODE,NULL,NULL,NULL])
        self._sendByteArr(byteArr,self.default_timeout)
        byteArr = self._readBytes(timeout=self.default_timeout)
        self._close_port()
        if byteArr[1] == ERROR:
            raise SlideError('Error trying to get the setting byte')
        
        # if 7th bit is set, we have been homed
        if byteArr[2] & 128:
            return True
        else:
            return False
        
    def _move_absolute(self,nstep):
        """
        move to a defined position in microsteps
        """
        if nstep < MIN_MS or nstep > MAX_MS:
            raise SlideError("Attempting to set position = %d ms," + \
                                 " which is out of range %d to %d" % 
                             (nstep,MIN_MS,MAX_MS) )
        start_pos = self._getPosition()
        timeout = self._compute_timeout(nstep-start_pos)

        # encode command bytes into bytearray
        byteArr = self._encodeCommandData(nstep)

        # add bytes to define instruction at start of array
        byteArr.insert(0,chr(MOVE_ABSOLUTE))
        byteArr.insert(0,chr(UNIT))
        if not self.connected:
            self._open_port()
        self._sendByteArr(byteArr,self.default_timeout)
        byteArr = self._readBytes(timeout=timeout)
        self._close_port()
        self.report_position()

    def _move_relative(self,nstep):
        """
        move by nstep microsteps relative to the current position
        """

        # if this raises an error, so be it
        start_pos = self._getPosition()
        attempt_pos = start_pos+nstep
        if attempt_pos < MIN_MS or attempt_pos > MAX_MS:
            raise SlideError("Attempting to set position = %d ms," + \
                                 " which is out of range %d to %d" % 
                             (nstep,MIN_MS,MAX_MS) )
        timeout = self._compute_timeout(nstep)

        # encode command bytes into bytearray
        byteArr = self._encodeCommandData(nstep)

        # add bytes to define instruction at start of array
        byteArr.insert(0,chr(MOVE_RELATIVE))
        byteArr.insert(0,chr(UNIT))
        if not self.connected:
            self._open_port()
        self._sendByteArr(byteArr,self.default_timeout)
        byteArr = self._readBytes(timeout=timeout)
        self._close_port()
        self.report_position()        

    def home(self):
        """
        move the slide to the home position. This is needed after a power on
        to calibrate the slide
        """
        if self._hasBeenHomed():
            # if this throws an exception, then something is bad, so don't catch
            start_pos = self._getPosition()
            timeout = self._compute_timeout(start_pos)
        else:
            print('device position undefined: setting max timeout')
            timeout = MAX_TIMEOUT

        byteArr = self._encodeByteArr([UNIT,HOME,NULL,NULL,NULL,NULL])
        if not self.connected:
            self._open_port()
        self._sendByteArr(byteArr,self.default_timeout)
        byteArr = self._readBytes(timeout=timeout)
        self._close_port()
        if byteArr[1] == ERROR:
            raise SlideError('Error occurred setting to the home position')
        print('Slide returned to home position')
        

    def reset(self):
        """
        carry out the reset command, equivalent to turning the slide off and
        on again. The position of the slide will be lost and a home will be
        needed
        """
        byteArr = self._encodeByteArr([UNIT,RESET,NULL,NULL,NULL,NULL]) 
        if not self.connected: 
            self._open_port()
        self._sendByteArr(byteArr,self.default_timeout) 
        byteArr = self._readBytes(timeout=self.default_timeout) 
        self._close_port()
        return byteArr

    def restore(self):
        """
        carry out the restore command. restores the device to factory settings
        very useful if the device does not appear to function correctly
        """
        byteArr = self._encodeByteArr([UNIT,RESTORE,PERIPHERAL_ID,
                                       NULL,NULL,NULL])
        if not self.connected:
            self._open_port()
        self._sendByteArr(byteArr,self.default_timeout)
        byteArr = self._readBytes(timeout=self.default_timeout)
        self._close_port()
        return byteArr

    def disable(self):
        """
        carry out the disable command. disables the potentiometer preventing 
        manual adjustment of the device
        """
        byteArr = self._encodeByteArr([UNIT,SET_MODE,POTENTIOM_OFF,
                                       NULL,NULL,NULL])
        if not self.connected:
            self._open_port()
        self._sendByteArr(byteArr,self.default_timeout)
        byteArr = self._readBytes(timeout=self.default_timeout)
        self._close_port()
        return byteArr

    def enable(self):
        """
        carry out the enable command. enables the potentiometer allowing 
        manual adjustment of the device
        """
        byteArr = self._encodeByteArr([UNIT,SET_MODE,POTENTIOM_ON,
                                       NULL,NULL,NULL])
        if not self.connected:
            self._open_port()
        self._sendByteArr(byteArr,self.default_timeout)
        byteArr = self._readBytes(timeout=self.default_timeout)
        self._close_port()
        return byteArr

    def stop(self):
        """stop the slide"""
        byteArr = self._encodeByteArr([UNIT,STOP,NULL,NULL,NULL,NULL])
        if not self.connected:
            self._open_port()
        self._sendByteArr(byteArr,self.default_timeout)
        byteArr = self._readBytes(timeout=self.default_timeout)
        self._close_port()
        if byteArr[1] == ERROR:
            raise SlideError('Error stopping the slide')
        else:
            print('Slide Stopped')
            self.report_position()

    def park(self):
        # what is the park value in MS?
        nstep = MIN_MS + int( (MAX_MS-MIN_MS)*
                              (PARK_POS-MIN_PX)/(MAX_PX-MIN_PX) + 0.5 )
        self._move_absolute(nstep)
        
    def move_relative(self,amount,units):
        """
        move the slide by a relative amount.
        
        Available units are:
        MS - microsteps
        PX - pixels
        MM - millimeters
        """
        if units.upper() not in ['MS','PX','MM']:
            raise SlideError("unsupported units %s: " + \
                                 "only PX, MM or MS allowed" % units)

        if units.upper() == 'MS':
            nstep = int(amount)
        elif units.upper() == 'PX':
            nstep = int( (MAX_MS-MIN_MS)*amount / (MAX_PX-MIN_PX) + 0.5 )
        elif units.upper() == 'MS':
            nstep = int( (MAX_MS-MIN_MS)*amount / (MAX_MM-MIN_MM) + 0.5 )

        self._move_relative(nstep)

    def move_absolute(self,amount,units):
        '''move the slide to an absolute position.
        available units are:
        MS - microsteps
        PX - pixels
        MM - millimeters
        '''
        if units.upper() not in ['MS','PX','MM']:
            raise SlideError('unsupported units %s: only PX,' + \
                                 ' MM or MS allowed' % units)

        if units.upper() == 'MS':
            nstep = int(amount)
        elif units.upper() == 'PX':
            nstep = MIN_MS + int( (MAX_MS-MIN_MS)*
                                  (amount-MIN_PX) / (MAX_PX-MIN_PX) + 0.5 )
        elif units.upper() == 'MS':
            nstep = MIN_MS + int( (MAX_MS-MIN_MS)*
                                  (amount-MIN_MM) / (MAX_MM-MIN_MM) + 0.5 )

        self._move_absolute(nstep)
            
    def report_position(self):
        pos = self._getPosition()
        pos_mm = MIN_MM + (MAX_MM-MIN_MM)*(pos-MIN_MS)/(MAX_MS-MIN_MS)
        pos_px = MIN_PX + (MAX_PX-MIN_PX)*(pos-MIN_MS)/(MAX_MS-MIN_MS)
        print("Current position = %d ms, %f mm, %f pixels" % 
              (pos,pos_mm,pos_px))
