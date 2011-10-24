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

import os
import subprocess

PNGCRUSH = 'pngcrush'
OPTIPNG = 'optipng'
ADVDEF = 'advdef'

def check_optimizer_programs(optimize_level):
    """
    """
    path = os.environ.get('PATH').split(os.pathsep)
    
    def exists_in_path(prog):
        result = filter(lambda x: os.path.exists(os.path.join(x, prog)), path)
        return len(result) != 0

    for prog, l in [(PNGCRUSH,1), (ADVDEF, 2)]:
        if l <= optimize_level:
            if (not exists_in_path(prog)) and (not exists_in_path(prog + '.exe')):
                raise Exception("Optimization prog %s for level %d not found!" %
                    (prog, l))

def optimize_image(img_path, img_format, optimize_level):
    """
    """
    if img_format == 'png':
        if optimize_level >= 1:
            # we can't do an atomic replace here because windows is terrible
            # so instead, we make temp files, delete the old ones, and rename
            # the temp files. go windows!
            subprocess.Popen([PNGCRUSH, img_path, img_path + '.tmp'],
                stderr=subprocess.STDOUT, stdout=subprocess.PIPE).communicate()[0]
            os.remove(img_path)
            os.rename(img_path + '.tmp', img_path)

        if optimize_level >= 2:
            # the "-nc" it's needed to no broke the transparency of tiles
            # use -z4 if optimize level is 3 or higher
            recompress_option = '-z2' if optimize_level is 2 else '-z4'
            subprocess.Popen([ADVDEF, recompress_option, img_path],
                stderr=subprocess.STDOUT,
                stdout=subprocess.PIPE).communicate()[0]
