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

When working fully, this script talks to the ATC camera, data and file
servers, the filterwheel, the focal plane slide, the TNT TCS, and the
Lakeshore CCD temperature monitor. When testing away from the telcescope
any of these can be switched off.
"""

# core
import argparse, os, time, traceback
import Tkinter as tk
import tkFont, tkMessageBox, tkFileDialog
import logging, Queue, threading
import xml.etree.ElementTree as ET

# my stuff
import trm.drivers.config      as config
import trm.drivers.globals     as g
import trm.drivers.drivers     as drvs
import trm.drivers.slide       as slide
import trm.drivers.uspec       as uspec
import trm.drivers.filterwheel as fwheel
import trm.drivers.lakeshore   as lake

class SetWheel(object):
    """
    Callable object to define the command for
    setting the filter wheel on the menu
    """
    def __init__(self, wheel):
        self.wheel = wheel
        self.wc    = None

    def __call__(self):
        if g.cpars['filter_wheel_on']:
            if self.wc is None or not self.wc.winfo_exists():
                try:
                    self.wc = fwheel.WheelController(self.wheel)
                except Exception, err:
                    g.clog.warn('Failed to open filter control window')
                    g.clog.warn('Error = ' + str(err))
                    self.wc = None
            else:
                g.clog.info('There already is a wheel control window')
        else:
            g.clog.warn('Filter wheel access is OFF; see settings.')

class EditFilter(object):
    """
    Callable object to define the command for
    editing the filters on the menu.
    """
    def __init__(self):
        self.ef = None

    def __call__(self):
        if self.ef is None or not self.ef.winfo_exists():
            try:
                self.ef = fwheel.FilterEditor()
            except Exception, err:
                g.clog.warn('Failed to open filter editor window')
                g.clog.warn('Error = ' + str(err))
                self.ef = None
        else:
            g.clog.info('There already is a filter editor window')

class GUI(tk.Tk):
    """
    This class isolates all the gui components which helps to separate
    them from the rtplot server.
    """

    def __init__(self):

        # Create the main GUI
        tk.Tk.__init__(self)
        self.title('usdriver')
        self.protocol("WM_DELETE_WINDOW", self.ask_quit)

        # Style it
        drvs.addStyle(self)

        # We now create the various container widgets. The order here
        # is mostly a case of the most basic first which often need to
        # be passed to later ones. This is achieved using the globals
        # of the 'globals' sub-module.

        # Construct the command logging window
        g.clog = drvs.LabelGuiLogger('CMM', self, 5, 56, 'Command log')

        # Construct the response logging window
        g.rlog = drvs.LabelGuiLogger('RSP', self, 5, 56, 'Response log')

        # Instrument parameters frame.
        g.ipars = uspec.InstPars(self)

        # Run parameters frame
        g.rpars = uspec.RunPars(self)

        # The information frame (run and frame number, exposure time)
        g.info = drvs.InfoFrame(self)

        # Container frame for switch options, observe, focal plane slide and
        # setup widgets
        topLhsFrame = tk.Frame(self)

        # Focal plane slide frame
        g.fpslide = slide.FocalPlaneSlide(topLhsFrame)

        # Observing frame
        g.observe = uspec.Observe(topLhsFrame)

        # Setup frame.
        g.setup = drvs.InstSetup(topLhsFrame)

        # Count & S/N frame
        g.count = uspec.CountsFrame(self)

        # Astronomical information frame
        g.astro = drvs.AstroFrame(self)

        if g.cpars['ccd_temperature_on']:
            try:
                # CCD temperature
                g.lakeshore = lake.LakeFile()
            except Exception, err:
                g.clog.warn(str(err))
                g.clog.warn('Switching off Lakeshore access (settings)')
                g.cpars['ccd_temperature_on'] = False

        # Switcher frame to select between setup, observe, focal plane slide
        switch = drvs.Switch(topLhsFrame)

        # Pack vertically into the container frame
        switch.pack(pady=5,anchor=tk.W)
        g.setup.pack(pady=5,anchor=tk.W)

        # Format the left-hand side
        topLhsFrame.grid(row=0,column=0,sticky=tk.W+tk.N,padx=10,pady=10)
        g.count.grid(row=1,column=0,sticky=tk.W+tk.N,padx=10,pady=10)
        g.info.grid(row=2,column=0,sticky=tk.W+tk.N,padx=10,pady=10)
        g.clog.grid(row=3,column=0,sticky=tk.W,padx=10,pady=10)

        # Right-hand side
        g.ipars.grid(row=0,column=1,sticky=tk.W+tk.N,padx=10,pady=10)
        g.rpars.grid(row=1,column=1,sticky=tk.W+tk.N,padx=10,pady=10)
        g.astro.grid(row=2,column=1,sticky=tk.W+tk.N,padx=10,pady=10)
        g.rlog.grid(row=3,column=1,sticky=tk.W,padx=10,pady=10)

        # Top menubar. Features a 'Quit' option, a menu of configuration
        # settings, and a menu to access the filter wheel.
        menubar = tk.Menu(self)
        menubar.add_command(label="Quit", command=self.ask_quit)

        # Settings menu
        settingsMenu = tk.Menu(menubar, tearoff=0)

        # level of expertise
        expertMenu   = drvs.ExpertMenu(settingsMenu, g.observe, g.setup,
                                       g.ipars, g.fpslide)
        settingsMenu.add_cascade(label='Expert', menu=expertMenu)

        # Some boolean switches
        settingsMenu.add_checkbutton(
            label='Require run params',
            var=drvs.Boolean('require_run_params'))

        settingsMenu.add_checkbutton(
            label='Confirm HV gain',
            var=drvs.Boolean('confirm_hv_gain_on'))

        settingsMenu.add_checkbutton(
            label='Confirm target name change',
            var=drvs.Boolean('confirm_on_change'))

        settingsMenu.add_checkbutton(
            label='TCS on',
            var=drvs.Boolean('tcs_on'))

        settingsMenu.add_checkbutton(
            label='Servers on',
            var=drvs.Boolean('cdf_servers_on'))

        settingsMenu.add_checkbutton(
            label='Filter wheel on',
            var=drvs.Boolean('filter_wheel_on'))

        settingsMenu.add_checkbutton(
            label='Focal plane slide on',
            var=drvs.Boolean('focal_plane_slide_on'))

        settingsMenu.add_checkbutton(
            label='CCD temperature on',
            var=drvs.Boolean('ccd_temperature_on'))

        settingsMenu.add_checkbutton(
            label='Templates from servers',
            var=drvs.Boolean('template_from_server'))

        # we run a callback here in order to enable the start button
        # if appropriate
        settingsMenu.add_checkbutton(
            label='Assume servers initialised',
            var=drvs.Boolean('servers_initialised',
                             lambda flag: g.ipars.check() if flag else None))

        # find index of last item added to the menu to allow it to be
        # enabled/disabled.  also pass it through to the expert menu
        # so that its status is updated if that changes.
        lindex = settingsMenu.index(tk.END)
        if g.cpars['expert_level']:
            settingsMenu.entryconfig(lindex,state=tk.NORMAL)
        else:
            settingsMenu.entryconfig(lindex,state=tk.DISABLED)
        expertMenu.indices = [lindex]

        # Add to menubar
        menubar.add_cascade(label='Settings', menu=settingsMenu)

        # Now the filter menu
        filterMenu = tk.Menu(menubar, tearoff=0)

        # Filter selector. First create a FilterWheel
        g.wheel = fwheel.FilterWheel()

        # create the SetWheel, attach to the Filters label.
        # This allows you to change the filter
        setwheel = SetWheel(g.wheel)
        filterMenu.add_command(label='Change filter', command=setwheel)

        # and the filter editor
        filterMenu.add_command(label='Edit filters',
                               command=lambda : fwheel.FilterEditor())

        menubar.add_cascade(label='Filters', menu=filterMenu)

        # Stick the menubar in place
        self.config(menu=menubar)

        # All components defined. Try to load previously stored settings
        settings = os.path.join(os.path.expanduser('~'),'.usdriver',
                                'settings.xml')
        if os.path.isfile(settings):
            try:
                xml = ET.parse(settings).getroot()
                g.ipars.loadXML(xml)
                g.rpars.loadXML(xml)
                g.clog.info('Loaded instrument and run settings from '
                            + settings)
            except Exception, err:
                g.clog.warn('Failed to load saved settings.')
                g.clog.warn(str(err))

        # run instrument setting checks
        g.ipars.check()

        if g.cpars['rtplot_server_on']:
            # the rtplot server is tricky since it needs to run all the time
            # along with the GUI which brings in issues such as concurrency,
            # threads etc.
            try:
                q = Queue.Queue()
                t = threading.Thread(target=self.startRtplotServer, args=[q,])
                t.daemon = True
                t.start()
                g.clog.info('rtplot server started on port ' + str(g.cpars['rtplot_server_port']))
            except Exception, e:
                g.clog.error('Problem trying to start rtplot server: ' + str(e))
        else:
            g.clog.info('rtplot server was not started')

        if g.cpars['file_logging_on']:
            # get name of file to log messages to. If set
            # it will be connected
            g.logfile = tkFileDialog.asksaveasfilename(
                initialdir=g.cpars['log_file_directory'],
                defaultextension='.log', filetypes=[('log files', '.log'),],
                title='Name of usdriver log file')

            if g.logfile:
                # update the loggers
                g.clog.update(g.logfile)
                g.rlog.update(g.logfile)
                g.fpslide.log.update(g.logfile)
            else:
                g.clog.info('Will not log usdriver messages')

        else:
            g.clog.warn('Logging to a file is disabled')

        self.update()

    def update(self):
        """
        Run regular checks on the FIFO queue which stores
        Exceptions thrown in threaded operations
        """
        try:
            exc = g.FIFO.get(block=False)
        except Queue.Empty:
            pass
        else:
            error, tback = exc
            g.clog.warn('Error in thread: ' + error)
            g.clog.debug(tback)

        self.after(2000, self.update)

    def startRtplotServer(self, x):
        """
        Starts up the server to handle GET requests from rtplot
        It is at this point that we pass the window parameters
        to the server.
        """
        self.server = drvs.RtplotServer(g.ipars, g.cpars['rtplot_server_port'])
        self.server.run()

    def ask_quit(self):
        """
        This is the close down routine
        """

        if g.cpars['confirm_on_quit'] and \
           not tkMessageBox.askokcancel('Quit', 'Really quit usdriver?'):
            g.clog.warn('Quit usdriver cancelled.')
        else:

            # try to close the filter wheel; trap errors
            try:
                if g.wheel.connected:
                    g.wheel.close()
                    g.clog.warn('closed filter wheel')
            except Exception, err:
                g.clog.warn('Error closing filter wheel: ' + str(err))


            try:

                # Save current configuration and run and instrument settings.
                # Files are saved to hidden directory in home directory.
                config_dir = os.path.join(os.path.expanduser('~'),'.usdriver')
                if not os.path.exists(config_dir):
                    os.makedirs(config_dir)

                # Save configuration (- 'servers_initialised' as one would
                # never want this to be True on entry). We save the config
                # file first since it does need the servers to be running.
                del g.cpars['servers_initialised']

                # Reset expert mode to beginner
                g.cpars['expert_level'] = 0

                conf = os.path.join(config_dir, 'usdriver.conf')
                config.writeCpars(config.ULTRASPEC, conf)
                g.clog.info('Saved usdriver configuration to ' + conf)

                try:

                    # Save current settings
                    root  = uspec.createXML(False)
                    settings = os.path.join(config_dir, 'settings.xml')
                    ET.ElementTree(root).write(settings)
                    g.clog.info('Saved instrument and run settings to ' +
                                    settings)
                except Exception, err:
                    g.clog.warn("""
Failed to save the instrument settings to disk. This
could be because you have already killed the servers
which are needed to define the XML to save the settings.
This is not a disaster, so the program will still exit
but in future, exit usdriver before ctrl-C-ing the
server windows.
""")
                    time.sleep(2)

                self.destroy()

            except Exception, err:
                g.clog.warn("""
Failed to save the usdriver configuration to disk.
Directory of saved files should be = {0}.
Please check that this directory is writeable and try
again. Failure to save the configuration could cause
the filters to become mis-labelled on next startup. If
you cannot get it to work, then at least note down the
current order of the filters before hitting ctrl-C.
Error = ' {1}\n""".format(config_dir, str(err)))


if __name__ == '__main__':

    # Default configuration file (which may not exist)
    def_cpars = os.path.join(os.path.expanduser('~'),'.usdriver',
                             'usdriver.conf')

    # command-line parameters
    parser = argparse.ArgumentParser(description=usage)

    # optional
    parser.add_argument('-c', dest='cpars', default=def_cpars,
                        help='configuration file name')

    try:
        # OK, parse arguments
        args = parser.parse_args()

        # Read a configuration file, if there is one
        try:
            config.readCpars(config.ULTRASPEC, args.cpars)
            print('Loaded configuration from ' +  args.cpars)

        except KeyError, err:
            print('Failed to load configuration from  ' +  args.cpars)
            print('KeyError = ' + str(err))
            print('Possibly a corrupt configuration file.')
            print('Will start with a default configuration;' +
                  ' a config file will be saved on exit.\n')
            config.loadCpars(config.ULTRASPEC)
        except IOError, err:
            print('Failed to load configuration from  ' +  args.cpars)
            print('Error = ' + str(err))
            print('Will start with a default configuration;' +
                  ' a config file will be saved on exit.\n')
            config.loadCpars(config.ULTRASPEC)

        # add one extra that there is no point getting from a file as
        # it should always be set False on starting the GUI
        g.cpars['servers_initialised'] = False

        if g.cpars['debug']:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        # The main window.
        gui = GUI()
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
