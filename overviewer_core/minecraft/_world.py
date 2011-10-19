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

import os.path
import cPickle
import nbt
import glob

"""
Notes:
path = non-absolute path to a file or dir, may or may not include a directory part
filename = only the basename/filename, should only be used for files
dirname = only the dirname/name of the directory, does not include parent directory
Xfile = object representing a file
Xfilename = corresponding filename for X
Xpath = corresponding path for X
"""

class World(object):
    """Represents a collection of dimensions (region sets)
    """

    #TODO dict-like region set access?

    LEVEL_FILE          = 'level.dat'
    #TODO document this, not sure what it is
    DATA_VERSION        = 19132
    BIOME_FILENAME_TPL  = 'b.%d.%d.biome'
    BIOME_DIR_NAME      = 'biomes'

    def __init__(self, path, **kwargs):
        self.path = path
        self._region_sets = dict(map(
            lambda region_set: return (region_set.name, region_set),
            self._get_region_sets()))
        self._data = nbt.load(os.path.join(self.path, self.LEVEL_FILE))[0]['Data']
        if not self._check_data_version():
            #TODO better way to handle this (VersionException or something)
            logging.error("Sorry, This version of Minecraft-Overviewer only works with the new McRegion chunk format")
            raise Exception("exit 1")

    def get_region_set(self, name):
        """Get a RegionSet object by region name.
        """
        #TODO this is completely wrong, region sets won't have names because
        # they don't have level.dats, unless we use the directory name as their
        # name
        return self._region_sets[name]

    def general_biome_data_available(self):
        """Check if any biome data is available at all
        """
        return len(glob.glob(os.path.join(self.world.path, self.BIOME_DIR_NAME,
            self.BIOME_FILENAME_TPL.replace('%d', '*'))) > 0

    def region_biome_data_available(self, regionX, regionY):
        """Check if biome data exists for a specific region
        """
        return os.path.exists(self._get_biome_data_path(regionX, regionY))

    def _get_biome_data_path(self, regionX, regionY):
        """Get the path for a biome data file
        """
        return os.path.join(self.world.path, self.BIOME_DIR_NAME,
            self.BIOME_FILENAME_TPL % (regionX, regionY))

    def get_biome_data(self, chunkX, chunkY):
        """
        """
        pass

    def _get_region_set_paths(self):
        """Get a list of dirs in this worlds path for dirs with region files
        in them
        """
        #TODO cache this? also, it's probably horribly inefficient
        # find all region files, run dirname on them, remove dupes
        #probably faster to walk path manually
        return list(set(map(os.path.dirname, os.path.join(
            self.path, '*', RegionSet.REGION_FILENAME_TPL.replace('%d', '*')))))

    def _get_region_sets(self):
        """Get a list of RegionSet objects for every region set path in
        _get_region_set_paths()
        """
        region_sets = []
        for path in self._get_region_set_paths():
            region_sets.append(RegionSet(self,
                path, self._config.get('region_set_config', {})))
        return region_sets
        
    def _check_data_version(self):
        return 'version' in data and data['version'] == self.DATA_VERSION

    def get_spawn_point(self):
        """Get the spawn point from level.dat, this not necessarily where
        the player marker will be placed and will likely differ slightly from
        where players actually spawn.
        """
        #TODO implement this
        data = nbt.load(os.path.join(self.path, self.LEVEL_FILE))[1]['Data']
        return map(int,[data['SpawnX'], data['SpawnY'], data['SpawnZ']])
