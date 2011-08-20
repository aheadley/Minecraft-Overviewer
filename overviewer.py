#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    This file is part of the Minecraft Overviewer.
#
#    Minecraft Overviewer is free software: you can redistribute it and/or
#    modify it under the terms of the GNU General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or (at
#    your option) any later version.
#
#    Minecraft Overviewer is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
#    Public License for more details.
#
#    You should have received a copy of the GNU General Public License along
#    with the Overviewer.  If not, see <http://www.gnu.org/licenses/>.

OK          = 0
BAD_VERSION = 16
BAD_CEXT    = 17
MISSING_CEXT= 18
OLD_CEXT    = 19
MISSING_WARG= 32
BAD_WARG    = 33
MISSING_OARG= 34
EXTRA_ARG   = 35
OPT_CONFLICT= 48

import sys
if sys.version_info[0] >= 3:
    print("Overviewer is not (yet) compatible with Python 3.x")
    sys.exit(BAD_VERSION)
elif not (sys.version_info[0] == 2 and sys.version_info[1] >= 6):
    print("Overviewer requires Python 2.6 or later")
    sys.exit(BAD_VERSION)

import os
import os.path
import re
import subprocess
import multiprocessing
import time
import logging
import platform
from overviewer_core import util

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s")

pdir = util.get_program_path()

# make sure the c_overviewer extension is available
try:
    from overviewer_core import c_overviewer
except ImportError, err:
    # if this is a frozen windows package, the following error messages about
    # building the c_overviewer extension are not appropriate
    if hasattr(sys, "frozen"):
        print("Somethign has gone wrong importing the c_overviewer extension. \
Please make sure the 2008 and 2010 redistributable packages from Microsoft are \
installed.")
        sys.exit(BAD_CEXT)
    # try to find the build extension
    ext = os.path.join(pdir, "overviewer_core", "c_overviewer.")
    if platform.system() == "Windows":
        ext += "pyd"
    else:
        ext += "so"
    if os.path.exists(ext):
        print("Error importing the c_overviewer extension: %s" % err)
        print("Please make sure it is up-to-date (clean and rebuild")
        sys.exit(BAD_CEXT)
    else:
        print("Unable to locate c_overviewer extension, please compile it by \
running `python setup.py build`, or see the README file for details.")
        import traceback
        traceback.print_exc()
        sys.exit(MISSING_CEXT)

if hasattr(sys, "frozen"):
    pass # we don't bother with a compat test since it should always be in sync
elif "extension_version" in dir(c_overviewer):
    # check to make sure the binary matches the headers
    if os.path.exists(os.path.join(pdir, "overviewer_core", "src", "overviewer.h")):
        with open(os.path.join(pdir, "overviewer_core", "src", "overviewer.h")) as f:
            lines = f.readlines()
            lines = filter(lambda x: x.startswith("#define OVERVIEWER_EXTENSION_VERSION"), lines)
            if lines:
                l = lines[0]
                if int(l.split()[2].strip()) != c_overviewer.extension_version():
                    print("Please rebuild your c_overviewer module.  It is out of date!")
                    sys.exit(OLD_CEXT)
else:
    print("Please rebuild your c_overviewer module.  It is out of date!")
    sys.exit(OLD_CEXT)

from overviewer_core.configParser import ConfigOptionParser
from overviewer_core import optimizeimages, world, quadtree
from overviewer_core import googlemap, rendernode


helptext = "%prog [OPTIONS] <World # / Name / Path to World> <tiles dest dir>"

def main():
    try:
        cpus = multiprocessing.cpu_count()
    except NotImplementedError:
        cpus = 1
    
    avail_rendermodes = c_overviewer.get_render_modes()
    avail_north_dirs = ['lower-left', 'upper-left', 'upper-right', 'lower-right', 'auto']
    
    parser = ConfigOptionParser(usage=helptext, config="settings.py")
    parser.add_option("-V", "--version",
        dest="version",
        helptext="Displays version information and then exits",
        action="store_true")
    parser.add_option("-p", "--processes",
        dest="procs",
        helptext="How many worker processes to start. Default %s" % cpus,
        default=cpus,
        action="store",
        type="int")
    parser.add_option("-z", "--zoom",
        dest="zoom",
        helptext="Sets the zoom level manually instead of calculating it. This \
can be useful if you have outlier chunks that make your world too big. This \
value will make the highest zoom level contain 2**(2*ZOOM) tiles",
        action="store",
        type="int",
        advanced=True)
    parser.add_option("--regionlist",
        dest="regionlist",
        helptext="A file containing, on each line, a path to a regionlist to \
update. Instead of scanning the world directory for regions, it will just use \
this list. Normal caching rules still apply.")
    parser.add_option("--forcerender",
        dest="forcerender",
        helptext="Force re-rendering the entire map (or the given regionlist). \
Useful for re-rendering without deleting it.",
        action="store_true")
    parser.add_option("--rendermodes",
        dest="rendermode",
        helptext="Specifies the render types, separated by commas. Use \
--list-rendermodes to list them all.",
        type="choice",
        choices=avail_rendermodes,
        required=True,
        default=avail_rendermodes[0],
        listify=True)
    parser.add_option("--list-rendermodes",
        dest="list_rendermodes",
        action="store_true",
        helptext="List available render modes and exit.",
        commandLineOnly=True)
    parser.add_option("--imgformat",
        dest="imgformat",
        helptext="The image output format to use. Currently supported: png \
(default), jpg.",
        advanced=True)
    parser.add_option("--imgquality",
        dest="imgquality",
        default=95,
        helptext="Specify the quality of image output when using imgformat=\"jpg\".",
        type="int",
        advanced=True)
    parser.add_option("--bg-color",
        dest="bg_color",
        helptext="Configures the background color for the GoogleMap output. \
Specify in #RRGGBB format",
        advanced=True,
        type="string",
        default="#1A1A1A")
    parser.add_option("--optimize-img",
        dest="optimizeimg",
        helptext="If using png, perform image file size optimizations on the \
output. Specify 1 for pngcrush, 2 for pngcrush+advdef and 3 for pngcrush-advdef \
with more agressive settings. This may double (or more) render times, but will \
produce up to 30% smaller images. NOTE: requires corresponding programs in $PATH \
or %PATH%",
        advanced=True)
    parser.add_option("--web-assets-hook",
        dest="web_assets_hook",
        helptext="If provided, run this function after the web assets have been \
copied, but before actual tile rendering begins. It should accept a QuadtreeGen \
object as its only argument.",
        action="store",
        metavar="SCRIPT",
        type="function",
        advanced=True)
    parser.add_option("--web-assets-path",
        dest="web_assets_path",
        helptext="Specifies a non-standard web_assets directory to use. Files \
here will overwrite the default web assets.",
        metavar="PATH",
        type="string",
        advanced=True)
    parser.add_option("--textures-path",
        dest="textures_path",
        helptext="Specifies a non-standard textures path, from which terrain.png \
and other textures are loaded.",
        metavar="PATH",
        type="string",
        advanced=True)
    parser.add_option("-q", "--quiet",
        dest="quiet",
        action="count",
        default=0,
        helptext="Print less output. You can specify this option multiple times.")
    parser.add_option("-v", "--verbose",
        dest="verbose",
        action="count",
        default=0,
        helptext="Print more output. You can specify this option multiple times.")
    parser.add_option("--skip-js",
        dest="skipjs",
        action="store_true",
        helptext="Don't output marker.js or regions.js")
    parser.add_option("--no-signs",
        dest="nosigns",
        action="store_true",
        helptext="Don't output signs to markers.js")
    parser.add_option("--north-direction",
        dest="north_direction",
        action="store",
        helptext="Specifies which corner of the screen north will point to. \
Defaults to whatever the current map uses, or lower-left for new maps. Valid \
options are: " + ", ".join(avail_north_dirs) + ".",
        type="choice",
        default="auto",
        choices=avail_north_dirs)
    parser.add_option("--display-config",
        dest="display_config",
        action="store_true",
        helptext="Display the configuration parameters, but don't render the map. \
Requires all required options to be specified",
        commandLineOnly=True)
    #parser.add_option("--write-config",
        #dest="write_config",
        #action="store_true",
        #helptext="Writes out a sample config file",
        #commandLineOnly=True)

    options, args = parser.parse_args()

    logging.getLogger().setLevel(
        logging.getLogger().level + 10 * options.quiet)
    logging.getLogger().setLevel(
        logging.getLogger().level - 10 * options.verbose)

    if options.version:
        try:
            import overviewer_core.overviewer_version as overviewer_version
            print("Minecraft-Overviewer %s" % overviewer_version.VERSION)
            print("Git commit: %s" % overviewer_version.HASH)
            print("\tbuilt %s" % overviewer_version.BUILD_DATE)
            print("\ton %s %s" % (overviewer_version.BUILD_PLATFORM, overviewer_version.BUILD_OS))
        except:
            print("Version info not found")
        sys.exit(OK)

    if options.list_rendermodes:
        rendermode_info = map(c_overviewer.get_render_mode_info, avail_rendermodes)
        name_width = max(map(lambda i: len(i['name']), rendermode_info))
        for info in rendermode_info:
            print("{name:{0}} {description}".format(name_width, **info))
        sys.exit(OK)

    if options.advanced_help:
        parser.advanced_help()
        sys.exit(OK)

    if len(args) < 1:
        logging.error("World (path, name, or number) argument required.")
        parser.print_help()
        list_worlds()
        sys.exit(MISSING_WARG)
    worlddir = args[0]

    if not os.path.exists(worlddir):
        # world given is either world number, or name
        worlds = world.get_worlds()
        # if there are no worlds found at all, exit now
        if not worlds:
            logging.error("No worlds found.")
            parser.print_help()
            sys.exit(BAD_WARG)
        try:
            worldnum = int(worlddir)
            worlddir = worlds[worldnum]['path']
        except ValueError:
            # it wasn't a number or path, try using it as a name
            try:
                worlddir = worlds[worlddir]['path']
            except KeyError:
                # it's not a number, name, or path
                logging.error("Invalid world name or number: %s" % worlddir)
                parser.print_help()
                sys.exit(BAD_WARG)
        except KeyError:
            # it was an invalid number
            logging.error("Invalid world number: %d" % worldnum)
            parser.print_help()
            sys.exit(BAD_WARG)
    
    # final sanity check for worlddir
    if not os.path.exists(os.path.join(worlddir, 'level.dat')):
        logging.error("Invalid world path, no level.dat found.")
        sys.exit(BAD_WARG)

    if len(args) < 2:
        logging.error("Output path argument required.")
        sys.exit(MISSING_OARG)
    elif len(args) > 2:
        parser.print_help()
        logging.error("Exactly two arguments are required. Extra arguments: %s" %
            ', '.join(args[2:]))
        sys.exit(EXTRA_ARG)


    destdir = args[1]
    if options.display_config:
        # just display the config file and exit
        parser.display_config()
        sys.exit(OK)


    if options.regionlist:
        regionlist = map(str.strip, open(options.regionlist, 'r'))
    else:
        regionlist = None

    if options.imgformat:
        fmts = ('jpg', 'png')
        if options.imgformat not in fmts:
            logging.error("Unknown image format: %s" % options.imgformat)
            logging.error("Image format should be one of: %s" % ', '.join(fmts))
        else:
            imgformat = options.imgformat
    else:
        imgformat = 'png'

    if options.optimizeimg:
        optimizeimg = int(options.optimizeimg)
        optimizeimages.check_programs(optimizeimg)
    else:
        optimizeimg = None

    if options.north_direction:
        north_direction = options.north_direction
    else:
        north_direction = 'auto'
    
    logging.info("Welcome to Minecraft Overviewer!")
    logging.debug("Current log level: {0}".format(logging.getLogger().level))
   
    useBiomeData = os.path.exists(os.path.join(worlddir, 'biomes'))
    if not useBiomeData:
        logging.info("Biome data not available.")
    else:
        logging.info("Biome data found.")
    
    # First do world-level preprocessing
    w = world.World(worlddir, destdir, useBiomeData=useBiomeData,
        regionlist=regionlist, north_direction=north_direction)
    if north_direction == 'auto':
        north_direction = w.persistentData['north_direction']
        options.north_direction = north_direction
    elif w.persistentData['north_direction'] != north_direction and \
            not options.forcerender and not w.persistentDataIsNew:
        logging.error("Conflicting north-direction setting!")
        logging.error("Overviewer.dat gives previous north-direction as " +
            w.persistentData['north_direction'])
        logging.error("Requested north-direction was " + north_direction)
        logging.error("To change north-direction of an existing render, --forcerender must be specified")
        sys.exit(OPT_CONFLICT)
    
    w.go(options.procs)

    logging.info("Rending the following tilesets: %s", ",".join(options.rendermode))

    bgcolor = (int(options.bg_color[1:3],16), int(options.bg_color[3:5],16),
        int(options.bg_color[5:7],16), 0)

    # create the quadtrees
    # TODO chunklist
    q = []
    qtree_args = {
        'depth': options.zoom,
        'imgformat': imgformat,
        'imgquality': options.imgquality,
        'optimizeimg': optimizeimg,
        'bgcolor': bgcolor,
        'forcerender': options.forcerender
    }
    for rendermode in options.rendermode:
        if rendermode == 'normal':
            qtree = quadtree.QuadtreeGen(w, destdir, rendermode=rendermode,
                tiledir='tiles', **qtree_args)
        else:
            qtree = quadtree.QuadtreeGen(w, destdir, rendermode=rendermode,
                **qtree_args)
        q.append(qtree)
    
    # do quadtree-level preprocessing
    for qtree in q:
        qtree.go(options.procs)

    # create the distributed render
    r = rendernode.RenderNode(q, options)
    
    # write out the map and web assets
    m = googlemap.MapGen(q, configInfo=options)
    m.go(options.procs)
    
    # render the tiles!
    r.go(options.procs)

    # finish up the map
    m.finalize()


def list_worlds():
    """Prints out a brief summary of saves found in the default directory"""
    worlds = world.get_worlds()
    if not worlds:
        logging.error("No worlds found in the default world locations")
        return
    logging.info("Detected worlds:")
    for name, info in sorted(worlds.iteritems()):
        if isinstance(name, basestring) and name.startswith("World") and len(name) == 6:
            try:
                world_n = int(name[-1])
                # we'll catch this one later, when it shows up as an
                # integer key
                continue
            except ValueError:
                pass
        timestamp = time.strftime("%Y-%m-%d %H:%M",
            time.localtime(info["LastPlayed"] / 1000))
        playtime = info["Time"] / 20
        playstamp = "%d:%02d" % (playtime / 3600, playtime / 60 % 60)
        size = "%.2fMB" % (info["SizeOnDisk"] / 1024. / 1024.)
        logging.info("World %s: %s Playtime: %s Modified: %s" %
            (name, size, playstamp, timestamp))


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
