#!/usr/bin/env python
from __future__ import print_function

usage = \
"""
Python replacement for usdriver GUI. 

Author: Tom Marsh

This allows you to define the windows and readout mode you want to use.
The window setup can be carried out at any time, including while a run
is exposing. Nothing is sent to the camera until you send the 'post' 
command.
"""

import argparse, os
import Tkinter as tk
import tkFont
import logging
import Queue
import threading

import trm.drivers as drvs
import trm.drivers.uspec as uspec
import trm.drivers.filterwheel as filterwheel

class GUI(tk.Tk):
    """
    This class isolates all the gui components which helps to separate
    them from the rtplot server.
    """

    def __init__(self, cpars):

        # Create the main GUI
        tk.Tk.__init__(self)
        self.title('usdriver')

        # Style it
        drvs.addStyle(self)

        # We now create the various container widgets. The order here
        # is mostly a case of the most basic first which often need to
        # be passed to later ones. This cannot entirely be followed however
        # see the 'share' dictionary below

        # First the loggers, command and response
        clog = drvs.LogDisplay(self, 5, 50, 'Command log')
        rlog = drvs.LogDisplay(self, 5, 56, 'Response log')

        # dictionary of objects to share. Used to pass the widgets 
        # from one to another. Basically a thinly-disguised global
        share = {'clog' : clog, 'rlog' : rlog, 'cpars' : cpars}

        # Instrument setup frame. 
        instpars  = uspec.InstPars(self, share)
        share.update({'instpars' : instpars})
        
        print('created instpars')

        # Run setup data frame
        runpars = uspec.RunPars(self, share)
        share.update({'runpars' : runpars})

        print('created runpars')

        # The information frame (run and frame number, exposure time)
        info = drvs.InfoFrame(self, share)
        share.update({'info' : info})

        print('created info')

        # Container frame for switch options, observe, focal plane slide and
        # setup widgets
        topLhsFrame = tk.Frame(self)

        # Focal plane slide frame
        fpslide = drvs.FocalPlaneSlide(topLhsFrame, share)
        share.update({'fpslide' : fpslide})

        # Observe frame: needed for the setup frame so defined first.
        observe = uspec.Observe(topLhsFrame, share)
        share.update({'observe' : observe})

        # Setup frame. Pass the actions frame to it. This
        # one is visible at the start.
        setup = drvs.InstSetup(topLhsFrame, share)
        share.update({'setup' : setup})

        # Count & S/N frame
        count = uspec.CountsFrame(self, share)
        share.update({'cframe' : count})

        # Astronomical information frame
        astro = drvs.AstroFrame(self, share)
        share.update({'astro' : astro})

        # Sub-frame to select between setup, observe, focal plane slide
        switch = drvs.Switch(topLhsFrame, share)

        # Pack vertically into the container frame
        switch.pack(pady=5,anchor=tk.W)
        setup.pack(pady=5,anchor=tk.W)

        # Format the left-hand side
        topLhsFrame.grid(row=0,column=0,sticky=tk.W+tk.N,padx=10,pady=10)
        count.grid(row=1,column=0,sticky=tk.W+tk.N,padx=10,pady=10)
        info.grid(row=2,column=0,sticky=tk.W+tk.N,padx=10,pady=10)
        clog.grid(row=3,column=0,sticky=tk.W,padx=10,pady=10)

        # Right-hand side
        instpars.grid(row=0,column=1,sticky=tk.W+tk.N,padx=10,pady=10)
        runpars.grid(row=1,column=1,sticky=tk.W+tk.N,padx=10,pady=10)
        astro.grid(row=2,column=1,sticky=tk.W+tk.N,padx=10,pady=10)
        rlog.grid(row=3,column=1,sticky=tk.W,padx=10,pady=10)

        # Top menubar
        menubar = tk.Menu(self)
        menubar.add_command(label="Quit", command=self.quit)

        # Settings menu
        settingsMenu = tk.Menu(menubar, tearoff=0)
        
        # level of expertise
        expertMenu   = drvs.ExpertMenu(settingsMenu, cpars, observe, setup)
        settingsMenu.add_cascade(label='Expert', menu=expertMenu)

        # Some boolean switches
        settingsMenu.add_checkbutton(
            label='Require run params',
            var=drvs.Boolean('require_run_params',cpars))

        settingsMenu.add_checkbutton(
            label='Confirm HV gain', 
            var=drvs.Boolean('confirm_hv_gain_on',cpars))

        settingsMenu.add_checkbutton(
            label='Confirm target', 
            var=drvs.Boolean('confirm_on_change',cpars))

        settingsMenu.add_checkbutton(
            label='Access TCS', 
            var=drvs.Boolean('access_tcs',cpars))

        # Add to menubar
        menubar.add_cascade(label='Settings', menu=settingsMenu)

        # Filter selector. First create a FilterWheel
        wheel = filterwheel.FilterWheel()

        class SetFilter(object):
            """
            Callable object to define the command for
            the Filters on the menu.
            """
            def __init__(self, wheel, share):
                self.wheel = wheel
                self.share = share
                self.wc    = None

            def __call__(self):
                if self.wc is None:
                    self.wc = \
						filterwheel.WheelController(self.wheel, self.share)
                else:
                    clog = self.share['clog']
                    clog.log.info('There is already a wheel control window')

        # create the SetFilter attach to the Filters label
        setfilt = SetFilter(wheel, share)
        menubar.add_command(label='Filters', command=setfilt)

        # Stick the menubar in place
        self.config(menu=menubar)

        # Everything now defined, so we can run checks
        instpars.check()

        # Save some attributes for setting up the rtplot server
        self.cpars    = cpars
        self.instpars = instpars

        if cpars['rtplot_server_on']:
            # the rtplot server is tricky since it needs to run all the time
            # along with the GUI which brings in issues such as concurrency,
            # threads etc.
            try:
                q = Queue.Queue()
                t = threading.Thread(target=self.startRtplotServer, args=[q,])
                t.daemon = True
                t.start()
                print('rtplot server started on port',
					  cpars['rtplot_server_port'])
            except Exception as e:
                print('Problem trying to start rtplot server:', e)
        else:
            print('rtplot server was not started')

    def startRtplotServer(self, x):
        """
        Starts up the server to handle GET requests from rtplot
        It is at this point that we pass the window parameters
        to the server.
        """
        self.server = drvs.RtplotServer(self.instpars, 
										self.cpars['rtplot_server_port'])
        self.server.run()


if __name__ == '__main__':

    # command-line parameters
    parser = argparse.ArgumentParser(description=usage)

    # positional
    # parser.add_argument('run', help='run to plot, e.g. "run045"')

    # optional
    parser.add_argument('-c', dest='cpars', default='usdriver.conf', 
                        help='configuration file name')
    
    try:
        # OK, parse arguments
        args = parser.parse_args()

        with open(args.cpars) as fp:
            cpars = drvs.loadCpars(fp)

        if cpars['debug']:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        # The main window.
        gui = GUI(cpars)
        gui.mainloop()

        # be nice on exit
        print('\nThank you for using usdriver')
        print('\nusdriver was brought to you by ULTRASPEC Productions')
        print('\n... delivering you a faster camera ...\n')

    except IOError, err:
        print('\nERROR:',err)
        print('You might want to use the -c option to specify the name')
        print('Script aborted.')
        exit(1)
