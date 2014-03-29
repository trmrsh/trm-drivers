#!/usr/bin/python

import sys
import getopt
import time
import re
from time import strftime
from time import localtime
import serial
import os
import popen2
import signal
  

def AsciiPrint( var, hdr="" ):
  print hdr,
  for a in var:
    print "[",ord(a),"]",
  print ""

# Lakshore device serial interface
class lake:
    def __init__(self, port='/dev/ttyS0'):
        self.com = serial.Serial(port, 9600, serial.SEVENBITS,
                                 serial.PARITY_ODD, serial.STOPBITS_ONE,
                                 2, 0, 0)
#        print self.com
        if not self.com.isOpen():
            self.com.open()
        self.com.flushInput()
        self.com.flushOutput()
        #self.com.close()

    def shutDown(self):
      if self.com.isOpen():
        self.com.close()

    def cmd(self, cmd):
#        print 'lake> command <%s>'%(cmd)
        tmp = cmd + '\r\n'
        if not self.com.isOpen():
            self.com.open()
        self.com.flushInput()
        self.com.flushOutput()
        #print "Command:",tmp
        #AsciiPrint(tmp, "Command: ")
        self.com.write(tmp)
        # Test
#        time.sleep(1)
#        n = self.com.inWaiting()
#        print 'lake> got ' + repr(n) + ' bytes'
#        rep = self.com.read(n)
        #
        rep = self.com.readline()
        #print "Reply:",rep
        rep = re.sub('\r', '', rep)
        rep = re.sub('\n', '', rep)
        return rep
#        rep = ''
#        l = self.com.read(1)
##        print 'lake> got <' + l + '>', ord(l)
#        while l not in ['\r','\n']:
#            rep = rep + l
#            l = self.com.read(1)
##        print 'lake> reply <%s>'%(rep)
#        self.com.close()
#        return rep

if __name__=='__main__':

    quiet = 0
    logfile = None
    output = None
    interval=0.0
    port='/dev/ttyS0'

    options = "hql:o:i:p:"
    long_options = ["help", "quiet", "logfile=", "output=", "interval=","port="]
    (optval, args) = getopt.getopt(sys.argv[1:],options, long_options)
    for (opt,val) in optval:
        if opt == "-q" or opt == "--quiet":
            quiet = 1 
        elif opt == "-l" or opt == "--logfile":
            logfile = val
        elif opt == "-l" or opt == "--logfile":
            output = val
        elif opt == "-i" or opt == "--interval":
            interval = float(val)
        elif opt == "-p" or opt == "--port":
            port = val
        else:
            print "Usage:"
            print "\t%s [--quiet] [--logfile=name] [--output=name] [--port=name] --interval=n" % sys.argv[0]
            print "interval is required, and represents a time in seconds (float value, minimum 1 second)"
            sys.exit(0)

    ls = lake(port)

    #ovveride Ctrl-c to shutdown cleanly
    def shutdown_handler(signal,frame):
      print 'shutting down cleanly'
      # kill old netcat processes
      os.system('kill `ps axww | grep "netcat_loop.tcsh" | grep -v grep | cut -c1-5` 2>/dev/null')
      os.system('kill `ps axww | grep "lakeshore_netcat.tcsh" | grep -v grep | cut -c1-5` 2>/dev/null')
      os.system('killall netcat 2> /dev/null')
      ls.shutDown()
      sys.exit(0)
    signal.signal(signal.SIGINT,shutdown_handler)
    signal.signal(signal.SIGHUP,shutdown_handler)
    #if len(sys.argv) < 2:
    #    print 'Missing interval argument!'
    #    sys.exit()
#
#    interval = sys.argv[1]
    if interval < 1.0:
        print "Invalid interval, try --help for a hint"
        sys.exit(1)

    # Create log file
    if output == None:
      output = strftime('Lakeshore_log%Y%m%d.csv', localtime())
      f = open('lakeshore_netcat.tcsh','w')
      f.write('#!/bin/tcsh\n')
      f.write('/usr/bin/tail -f /home/observer/Lakeshore/' + output + '\n')
      f.close()
      # kill old netcat processes
      os.system('kill `ps axww | grep "netcat_loop.tcsh" | grep -v grep | cut -c1-5` 2>/dev/null')
      os.system('kill `ps axww | grep "lakeshore_netcat.tcsh" | grep -v grep | cut -c1-5` 2>/dev/null')
      os.system('killall netcat 2> /dev/null')
      # launch tempmon2 server
      popen2.popen2('/bin/tcsh netcat_loop.tcsh &')

    if not quiet: print 'Creating temperature file %s'%(output)
    #print output

    msg = 'Day,Date,Month,Year,Time,Temp A(K),Temp B(K),Heater (%)'
    if not quiet: print msg

    version = ls.cmd('*IDN? ')
    #print "Lakeshore version:", version
    if ( os.path.exists(output) ):
      fp = open(output, 'a+')
    else:
      fp = open(output, 'w')
      fp.write(msg + '\n')
      fp.write("# Lakeshore version:" + version + '\n')
      fp.flush()
    fp.close()
    
    if not logfile == None:
        fp = open(logfile,"a+")
        fp.write(output+"\n")
        fp.close()

    while 1:
      try:
        tempa = ls.cmd('KRDG? A')
        tempb = ls.cmd('KRDG? B')
        heater = ls.cmd('HTR? ')
        ls.shutDown()

        # Display/log result
        now = strftime('%a,%d,%b,%Y,%H:%M:%S', localtime())
        msg = '%s,%s,%s,%s'%(now, tempa[1:], tempb[1:], heater[1:])
        if not quiet: print msg

        fp = open(output, 'a+')
        fp.write(msg + '\n')
        fp.flush()
        fp.close()

        time.sleep(float(interval))

      except Exception, err:
        print 'Error occurred accessing Lakeshore: ' + str(err)
        print 'Will try again in 1 second'
        time.sleep(1.)


    # Clean up
    fp.close()
