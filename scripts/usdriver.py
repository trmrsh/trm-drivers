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

def style(root):
    """
    Styles the GUI: global fonts and colours.
    """

    # Default font
    default_font = tkFont.nametofont("TkDefaultFont")
    default_font.configure(size=11)
    root.option_add('*Font', default_font)

    # Menu font
    menu_font = tkFont.nametofont("TkMenuFont")
    menu_font.configure(size=11)
    root.option_add('*Menu.Font', menu_font)

    # Entry font
    entry_font = tkFont.nametofont("TkTextFont")
    entry_font.configure(size=11)
    root.option_add('*Entry.Font', menu_font)

    # position and size
    #    root.geometry("320x240+325+200")

    # Default background colour
    root.option_add('*Background', drvs.COL_MAIN)
    root.option_add('*HighlightBackground', drvs.COL_MAIN)
    root.config(background=drvs.COL_MAIN)

#    root.option_add("*selectBackground", "gold")
    root.option_add("*focusForeground", "black")

class Switch(tk.Frame):
    """
    Class to switch between the actions and setup frames
    """
    def __init__(self, master, observe, setup):
        tk.Frame.__init__(self, master)

        self.val = tk.StringVar()
        self.val.set('Setup') 
        self.val.trace('w', self._changed)

        b = tk.Radiobutton(self, text='Setup', variable=self.val, value='Setup')
        b.grid(row=0, column=0, sticky=tk.W)
        b = tk.Radiobutton(self, text='Observe', variable=self.val, value='Observe')
        b.grid(row=0, column=1, sticky=tk.W)
        
        self.observe = observe
        self.setup     = setup

    def _changed(self, *args):
        if self.val.get() == 'Observe':
            self.setup.pack_forget()
            self.observe.pack(anchor=tk.W, pady=10)
        else:
            self.observe.pack_forget()
            self.setup.pack(anchor=tk.W, pady=10)
            

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description=usage)

    # positional
    # parser.add_argument('run', help='run to plot, e.g. "run045"')

    # optional
    parser.add_argument('-c', dest='confpars', default='usdriver.conf', type=argparse.FileType('r'), \
                            help='configuration file name')

    # parser.add_argument('-n', dest='nccd', type=int, default=0, help='CCD to plot (0 for all)')
    # parser.add_argument('-plo', type=float, default=2., help='Lower percentile for intensity display')
    # parser.add_argument('-r', dest='back', action='store_true', help='remove median background from each window')
    
    # OK, parse arguments
    try:
        args = parser.parse_args()
    except IOError, err:
        print('\nERROR: failed to load configuration file.')
        print('Error message from argument parser:',err)
        print('You might want to use the -c option to specify the name')
        print('Script aborted.')
        exit(1)

    # Load configuration parameters
    confpars = drvs.loadConfPars(args.confpars)

    # The main window.
    root = tk.Tk()
    root.title('usdriver')

    # set fonts, colours
    style(root)

    # Top menubar
    menubar = tk.Menu(root, bg=drvs.COL_MAIN)
    menubar.add_command(label="Quit", command=root.quit)
    root.config(menu=menubar)

    # Loggers for commands and responses
    commWindow = drvs.LogDisplay(root, 6, 50, 'Command log')
    commLogger = drvs.LoggingToGUI(commWindow)
    respWindow = drvs.LogDisplay(root, 6, 50, 'Response log')
    respLogger = drvs.LoggingToGUI(respWindow)

    # Frames for top-left- and top-right-hand sides
    topLhsFrame = tk.Frame(root)
    topRhsFrame = tk.Frame(root)

    # Stick into a grid, side by side.
    topLhsFrame.grid(row=0, column=0, sticky=tk.W+tk.N, padx=10)
    topRhsFrame.grid(row=0, column=1, sticky=tk.W+tk.N, padx=10)

    # Right-hand side first: 2 frames packed into a frame
    # at the top, 1 logger frame at the bottom

    # Instrument setup frame. The instOther is a container
    # for other objects that are accessed from within
    # the InstPars widget. In particular, changed to InstPars
    # have consequences for the Observe commands. At this
    # point, this is undefined, therefore we just have a
    # placeholder that will be updated later.
    instOther = {'confpars' : confpars, 'observe' : None}
    instpars  = uspec.InstPars(topRhsFrame, instOther)

    # Run setup data frame
    runpars = uspec.RunPars(topRhsFrame)

    # Pack vertically
    instpars.pack(pady=10,anchor=tk.W)
    runpars.pack(pady=10,anchor=tk.W)

    # Response window in bottom right
    respWindow.grid(row=1,column=1,sticky=tk.W,padx=10,pady=10)

    # Now the left-hand side: 2 frames at top, 1 logger
    # at the bottom.

    # Observe frame: needed for the setup frame so defined first.
    # observeOther serves the same purpose as instOther above
    observeOther = {'confpars' : confpars, 'instpars' : instpars, 
                      'runpars' : runpars, 'commLogger' : commLogger,
                      'respLogger' : respLogger}
    observe = uspec.Observe(topLhsFrame, observeOther)

    # Update instOther
    instOther['observe'] = observe

    # Setup frame. Pass the actions frame to it. This
    # one is visible at the start.
    setupOther =  {'confpars' : confpars, 'observe' : observe,
                   'commLogger' : commLogger, 'respLogger' : respLogger}
    setup = drvs.InstSetup(topLhsFrame, setupOther)

    # Sub-frame to select between setup or observe
    # Requires both of the previous two frames to have been set.
    switch = Switch(topLhsFrame, observe, setup)

    # Pack vertically
    switch.pack(pady=10)
    setup.pack(pady=10)

    # Command window in bottom left
    commWindow.grid(row=1,column=0,sticky=tk.W,padx=10,pady=10)

    # Finally, the big reveal
    root.mainloop()

    print('usdriver was brought to you by ULTRASPEC Productions')
    print('"Delivering you a faster camera ..."')
