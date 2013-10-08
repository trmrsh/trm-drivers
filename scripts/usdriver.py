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
import trm.drivers as drvs
import trm.drivers.uspec as uspec
import logging
import Queue
import threading

class GUI(tk.Tk):
    """
    This class isolates all the gui components which helps to separate
    them from the rtplot server.
    """

    def __init__(self, confpars):
        tk.Tk.__init__(self)
        self.title('usdriver')

        # Style the GUI
        drvs.addStyle(self)

        # The GUI has a grid layout with 3 rows by 2 columns. The bottom 
        # row is occupied by logger windows. Frames are used to group 
        # widgets. Top-left: either the basic setup commands or 
        # observing commands. Top-right: window and CCD parameters. 
        # Middle-left: information such as run number, exposure time. 
        # Middle-right: run parameters such as the target name.

        # First the loggers, command and response
        commLog = drvs.LogDisplay(self, 5, 50, 'Command log')
        respLog = drvs.LogDisplay(self, 5, 58, 'Response log')

        # The right-hand side

        # Instrument setup frame. "instOther" is a container
        # for other objects that are accessed from within
        # the InstPars widget. In particular, changes to InstPars
        # have consequences for the Observe commands. At this
        # point, they are undefined, therefore we just have a
        # placeholder that will be updated later.
        instOther = {'confpars' : confpars, 'observe' : None}
        instpars  = uspec.InstPars(self, instOther)

        # Run setup data frame
        runOther = {'commLog' : commLog, 'respLog' : respLog}
        runpars = uspec.RunPars(self, runOther)

        # Grid vertically
        instpars.grid(row=0,column=1,sticky=tk.W+tk.N,padx=10,pady=10)
        runpars.grid(row=1,column=1,sticky=tk.W+tk.N,padx=10,pady=10)
        respLog.grid(row=2,column=1,sticky=tk.W,padx=10,pady=10)

        # The left-hand side: 3 frames at top, 1 log
        # at the bottom. First frame simply provides switches 
        # 'setup' and 'observe' to allow switching of the second
        # between the two possibilities. The third frame is an 
        # information frame.

        # Kick off with some frames that have to be available to the 
        # observation frame



        # The information frame
        inother = {'confpars' : confpars, 'commLog' : commLog, 'respLog' : respLog}
        info = drvs.InfoFrame(self, inother)

        # Container frame for switch options and observe & setup parameters
        topLhsFrame = tk.Frame(self)

        # Focal plane slide frame
        fpother = {'confpars' : confpars, 'commLog' : commLog,
                   'respLog' : respLog, 'info' : info}
        fpslide = drvs.FocalPlaneSlide(topLhsFrame, fpother)

        # Observe frame: needed for the setup frame so defined first.
        # observeOther serves the same purpose as instOther above
        observeOther = {'confpars' : confpars, 'instpars' : instpars, 
                        'runpars' : runpars, 'commLog' : commLog,
                        'respLog' : respLog, 'info' : info}
        observe = uspec.Observe(topLhsFrame, observeOther)

        # Update instOther
        instOther['observe'] = observe

        # Setup frame. Pass the actions frame to it. This
        # one is visible at the start.
        setupOther =  {'confpars' : confpars, 'observe' : observe,
                       'commLog' : commLog, 'respLog' : respLog}
        setup = drvs.InstSetup(topLhsFrame, setupOther)

        # Sub-frame to select between setup or observe
        # Requires both of the previous two frames to have been set.
        switch = drvs.Switch(topLhsFrame, setup, fpslide, observe)

        # Pack vertically into the container frame
        switch.pack(pady=5,anchor=tk.W)
        setup.pack(pady=5,anchor=tk.W)

        # Now format the left-hand side: container frame, info and commLog
        # arranged in a vertical grid.
        topLhsFrame.grid(row=0,column=0,sticky=tk.W+tk.N,padx=10,pady=10)
        info.grid(row=1,column=0,sticky=tk.W+tk.N,padx=10,pady=10)
        commLog.grid(row=2,column=0,sticky=tk.W,padx=10,pady=10)

        # Create top menubar
        menubar = tk.Menu(self)
        menubar.add_command(label="Quit", command=self.quit)

        # Settings
        settingsMenu = tk.Menu(menubar, tearoff=0)
        expertMenu = drvs.ExpertMenu(settingsMenu, confpars, setup, observe)
        settingsMenu.add_cascade(label='Expert', menu=expertMenu)
        menubar.add_cascade(label='Settings', menu=settingsMenu)

        # Stick the menubar in place
        self.config(menu=menubar)

        # Save some attributes for setting up the rtplot server
        self.confpars = confpars
        self.instpars = instpars

        if confpars['rtplot_server_on']:
            # the rtplot server is tricky since it needs to run all the time
            # along with the GUI which brings in issues such as concurrency,
            # threads etc.
            try:
                q = Queue.Queue()
                t = threading.Thread(target=self.startRtplotServer, args=[q,])
                t.daemon = True
                t.start()
                print('rtplot server started on port',confpars['rtplot_server_port'])
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
        self.server = drvs.RtplotServer(self.instpars, self.confpars['rtplot_server_port'])
        self.server.run()


if __name__ == '__main__':

    # command-line parameters
    parser = argparse.ArgumentParser(description=usage)

    # positional
    # parser.add_argument('run', help='run to plot, e.g. "run045"')

    # optional
    parser.add_argument('-c', dest='confpars', default='usdriver.conf', type=argparse.FileType('r'), \
                            help='configuration file name')

    # parser.add_argument('-plo', type=float, default=2., help='Lower percentile for intensity display')
    # parser.add_argument('-r', dest='back', action='store_true', help='remove median background from each window')
    
    try:
        # OK, parse arguments
        args = parser.parse_args()

        # Load configuration parameters
        confpars = drvs.loadConfPars(args.confpars)

        if confpars['debug']:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        # The main window.
        gui = GUI(confpars)
        gui.mainloop()

        # be nice on exit
        print('\nThank you for using usdriver')
        print('\nusdriver was brought to you by ULTRASPEC Productions')
        print('\n... delivering you a faster camera ...\n')

    except IOError, err:
        print('\nERROR: failed to load configuration file.')
        print('Error message from argument parser:',err)
        print('You might want to use the -c option to specify the name')
        print('Script aborted.')
        exit(1)
