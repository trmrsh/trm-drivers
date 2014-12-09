#!/usr/bin/env python

"""
Defines configuration options, how to read them and save them.
"""

# The configuration for a given instrument consists of a list containing
# strings and two-element lists. The strings are comments, the lists contain
# configuration parameters and default values. The type of the default value
# defines what is allowed for that parameter. The comments are so that an
# understandable file is created when dumping to disk. The list preserves
# the order defined here.

import globals as g
import drivers as drvs

ULTRASPEC = \
    ["""
# Example configuration file for usdriver.py
#
# =========================================
#
#  Things that you may often want to change
#
# =========================================
#
# RTPLOT_SERVER_ON      = Whether to switch usdriver's server for rtplot on or not
#                         [YES/NO]. You may well want to use this while observing,
#                         probably not otherwise, not that it will do any harm.
#
# CDF_SERVERS_ON        = This controls enabling of all actions to do with the ATC
#                         servers. 'CDF' = camera, data, file. It does no harm to
#                         leave it on, but if you turn it off, it will prevent you
#                         from even trying to interact with the servers.
#
# FILTER_WHEEL_ON       = Toggles whether the program tries to interact with the filterwheel
#
# FOCAL_PLANE_SLIDE_ON  = Toggles whether the program tries to interact with the focal plane slide
#
# CCD_TEMPERATURE_ON    = Toggles access to CCD temperature sensor
#
# TCS_ON                = Toggles access to the TCS
#
# EXPERT_LEVEL          = 0 -- program stops you doing things out of order.
#                              Simplifies setup menu as far as possible.
#                         1 -- program still stops you doing things out of order,
#                              but offers a more detailed setup window.
#                         2 -- guru status: all buttons enabled. Its up to you to
#                              use them correctly.
#
# FILE_LOGGING_ON       = if yes, then (most) items printed in the left-hand
#                         short-format window are also sent to a file. They
#                         are appended if the file already exists. The file is
#                         written as an html table with times and could be
#                         useful information to retain after a run. Some error
#                         messages sent to the window may not be saved if they
#                         are of no interest except at the time of running.
#
# FILTER_NAMES          = list of filter names potentially available for ULTRASPEC;
#                         edit if a new filter is added.
#
# FILTER_IDS            = list of filter ids potentially available for ULTRASPEC;
#                         edit if a new filter is added.
#
# ACTIVE_FILTER_NAMES   = list of filters loaded into filter wheel: these *must* match what
#                         filters are actually in the wheel. If you are not sure, check
#                         them.
#
# TELINS_NAME           = name of telescope - instrument. Must correpond with one of
#                         the keys in trm.drivers.globals.TINS
""",
     ['rtplot_server_on', True],
     ['cdf_servers_on', True],
     ['filter_wheel_on', True],
     ['focal_plane_slide_on', True],
     ['ccd_temperature_on', True],
     ['tcs_on', True],
     ['expert_level', 0],
     ['file_logging_on', True],
     ['filter_names', ('N86', 'KG5','clear','NaI','u','g','r','i','z','iz',
                       'Bowen+HeII','rCont','Ha_broad','bCont','Ha_narr')],
     ['filter_ids', (32, 30, 7, 12, 18, 19, 20, 21, 22, 29, 31, 24, 25, 26, 27)],
     ['active_filter_names', ['KG5','g','r', 'i', 'z', 'iz']],
     ['telins_name', 'TNO-USPEC'],
     """
# ===========================================
#
#  Things you may occasionally want to change
#
# ===========================================
#
# HTTP_CAMERA_SERVER    = The URL of ULTRACAM camera server. The port number is
#                         unlikely to change but the rest of the URL could
#                         depending whether you run on the rack PC (localhost)
#                         or not.
#
# HTTP_DATA_SERVER      = URL of ULTRACAM data server. See comment on the camera
#                         server
#
# HTTP_FILE_SERVER      = URL of ULTRACAM file server (serves up data to rtplot)
#
# APP_DIRECTORY         = Initial directory on local machine to save applications
#                         to and load applications from.
#
# TEMPLATE_FROM_SERVER  = External template XML files are used to define instrument.
#                         These are used, e.g. when saving settings. This says whether
#                         they should come from the server (presumably more up-to-date)
#                         or from a local directory (see next).
#
# TEMPLATE_DIRECTORY    = Location of the template files, if they are to be taken from
#                         local machine rather than the server.
#
# LOG_FILE_DIRECTORY    = default directory for log files
#
# REQUIRE_RUN_PARAMS    = yes to force entry of run parameters before allowing
#                         posting of applications
#
# CONFIRM_ON_CHANGE     = yes to prompt a confirmation of the target name after
#                         any change of setup without a corresponding change of
#                         target. This is a safety device.
#
# CONFIRM_HV_GAIN_ON    = yes to prompt a confirmation when there has been any
#                         change of setup and the HV gain is on.
#
# DEBUG                 = enables reporting diagnostic output
#
# RTPLOT_SERVER_PORT    = port number for rtplot server
#
# FOCAL_PLANE_SLIDE     = path to focal plane slide command
#
# CONFIRM_ON_QUIT       =  yes to prompt confirmation whenever you try to quit
#                          usdriver.
#
# MDIST_WARN            = number of degrees from Moon at which to warn
""",
     ['http_camera_server', 'http://localhost:9980/'],
     ['http_data_server', 'http://localhost:9981/'],
     ['http_file_server', 'http://localhost:8007/'],
     ['app_directory', 'data/applications'],
     ['template_from_server', False],
     ['template_directory', 'data/templates'],
     ['log_file_directory', '~/.usdriver/logs'],
     ['require_run_params', True],
     ['confirm_on_change', True],
     ['confirm_hv_gain_on', True],
     ['debug', True],
     ['rtplot_server_port', 5100],
     ['confirm_on_quit', False],
     ['mdist_warn', 15.],
     """
# ===============================
#
# Things you should rarely change
#
# ===============================
#
#
# TEMPLATE_LABEL        = Intelligible names of general application types acting as templates
#
# TEMPLATE_PAIR         = Number of adjustable windows/window pairs corresponding to each template
#
# TEMPLATE_APP          = names of template XML files, in same order as in TEMPLATE_LABELS 
#
# TEMPLATE_ID           = values that will be used to check the basic type of an application
#                         from the XML
#
# POWER_ON_APP          = name of the power on application
#
# POWER_OFF_APP         = name of the power off application
#
# INSTRUMENT_APP        = Generic application for server setup
""",
     ['template_labels', ('Windows', 'Drift')],
     ['template_pairs', (4, 1)],
     ['template_apps', ('ccd201_winbin_app.xml', 'ccd201_driftscan_app.xml')],
     ['template_ids', ('ccd201_winbin_app', 'ccd201_driftscan_app')],
     ['power_on_app','ccd201_pon_cfg.xml'],
     ['power_off_app','ccd201_pof_cfg.xml'],
     ['instrument_app', 'ultraspec.xml'],
     ]

def fix_templates():
    """
    Special code for the templates. Converts configuration entries of the
    form template_* where * = labels, pairs, apps and ids, into a dictionary
    keyed by the label
    """
    if 'template_labels' in g.cpars and 'template_pairs' in g.cpars and \
            'template_apps' in g.cpars and 'template_ids' in g.cpars:
        labels = g.cpars['template_labels']
        pairs  = g.cpars['template_pairs']
        apps   = g.cpars['template_apps']
        ids    = g.cpars['template_ids']

        g.cpars['templates'] = dict( \
            (label,{'pair' : pair, 'app' : app, 'id' : id}) \
                for label,pair,app,id in zip(labels,pairs,apps,ids))

        # Next line is so that we know the order defined in the file
        g.cpars['template_labels'] = labels
        del g.cpars['template_pairs']
        del g.cpars['template_apps']
        del g.cpars['template_ids']
    else:
        drvs.DriverError('config.fix_templates: one of the four template lines was not present')

def unfix_templates():
    """
    Reverse of fix_templates to allow stuff
    to be written to disk.
    """
    pairs = []
    apps  = []
    ids   = []
    t = g.cpars['templates']
    for label in g.cpars['template_labels']:
        pairs.append(t[label]['pair'])
        apps.append(t[label]['app'])
        ids.append(t[label]['id'])

    g.cpars['template_pairs'] = pairs
    g.cpars['template_apps']  = apps
    g.cpars['template_ids']   = ids
    del g.cpars['templates']

def readCpars(guide, fname):
    """Loads dictionary of configuration parameters from a file 'fname'
    consisting of a series of entries of the form::

      key = value

    or::

      key = value1; value2; value3

    or::

      key = value1; value2; value3;
            value4; value5

    Take care with '=' and ';' because of their special meanings. '#' at the
    start of a line denotes a comment. A ';' at the end of a line indicates
    more values will follow in the next line.

    The routine loads the values straight into the global cpars as a
    dictionary.  The values it looks for and their types are defined by
    'guide' which contains a list. See config.ULTRASPEC for an example.

    """

    # first load the file into a dictionary
    item = {}
    with open(fname) as fp:
        more_values = False
        for line in fp:
            line = line.strip()

            if line.find('=') > -1:
                # standard key = value line
                more_values = False
                equals = line.find('=')
                key   = line[:equals].strip().lower()
                value = line[equals+1:].strip()
                if value.find(';') > -1:
                    if value[-1] == ';':
                        item[key] = value[:-1].split(';')
                        more_values = True
                    else:
                        item[key] = value.split(';')
                else:
                    item[key] = value

            elif more_values:
                # continuation line
                if line.find(';') > -1:
                    if line[-1] == ';':
                        item[key] += line[:-1].split(';')
                    else:
                        item[key] += line.split(';')
                        more_values = False
                else:
                    item[key] += [line]
                    more_values = False

            else:
                more_values = False



    # intialise the configuration parameters dictionary
    g.cpars = {}

    for entry in guide:
        if isinstance(entry, (list, tuple)):
            key, value = entry
            if isinstance(value,bool):
                if item[key].lower() == 'false' or item[key] == '0' or \
                   item[key].lower() == 'no':
                    g.cpars[key.lower()] = False
                elif item[key].lower() == 'true' or item[key] == '1' or \
                     item[key].lower() == 'yes':
                    g.cpars[key.lower()] = True
                else:
                    raise drvs.DriverError('Could not understand: ' + key + \
                                           ' = ' + item[key] + ' as a bollean')
            elif isinstance(value,str):
                g.cpars[key.lower()] = item[key]
            elif isinstance(value,int):
                g.cpars[key.lower()] = int(item[key])
            elif isinstance(value,float):
                g.cpars[key.lower()] = float(item[key])
            elif isinstance(entry, (list, tuple)):
                # all items of lists and tuples assumed to be strings
                g.cpars[key.lower()] = [x.strip() for x in item[key]]

    fix_templates()

def loadCpars(guide):
    """
    Loads dictionary of configuration parameters from a default guide such as
    config.ULTRASPEC. This is used when there is no file to read.

    """

    # intialise dictionary
    g.cpars = {}

    for entry in guide:
        if isinstance(entry, (list, tuple)):
            key, value = entry
            g.cpars[key.lower()] = value

    fix_templates()

def writeCpars(guide, fname):
    """
    Writes the configuration parameters to a file 'fname'. 'guide'
    is a template which contains comments to make the file readable
    """

    with open(fname, 'w') as fout:

        unfix_templates()
        for entry in guide:
            if isinstance(entry, str):
                fout.write(entry)
            elif isinstance(entry, (list, tuple)):
                key   = entry[0]
                value = g.cpars[key]
                if isinstance(value,(list,tuple)):
                    fout.write(key.upper() + ' = ' + '; '.join([str(v) for v in value]) + '\n')
                elif isinstance(value,bool):
                    if value:
                        fout.write(key.upper() + ' = yes\n')
                    else:
                        fout.write(key.upper() + ' = no\n')
                else:
                    fout.write(key.upper() + ' = ' + str(value) + '\n')

        fix_templates()
