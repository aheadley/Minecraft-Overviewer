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
    BIOME_FILENAME_TPL  = 'b.%d.%d.biome'
    BIOME_DIR_NAME      = 'biomes'

    def __init__(self, path, **kwargs):
        self.path = path
        self._region_sets = dict(map(
            lambda region_set: return (region_set.name, region_set),
            self._get_region_sets()))

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
            
class RegionSet(object):
    """Represents the set of region files that make up a single dimension in a
    world.
    """
    
    SETTINGS_FILE       = 'overviewer.dat'
    #these should probably be filename templates
    REGION_FILENAME_TPL = 'r.%d.%d.mcr'

    DEFAULT_DATA        = {}
    
    REGION_FILE_LIMIT   = 256
    #TODO i don't even know what these are used for
    CHUNK_X_LIMIT       = 1024
    
    def __init__(self, world, path, **kwargs):
        self.world = world
        self.name = self._get_name(path)
        if self.world.path[:len(path)] == path:
            self.path = path
        else:
            #the world path doesn't contain the region set path, this should
            #  probably never happen
            #TODO pick better exception
            raise Exception("RegionSet.path ({0}) not in World.path ({1})".format(
                path, self.world))
        self.path = os.join(self.world.path, path)
        self._persistent_data = self.DEFAULT_DATA
        try:
            self._persistent_data.update(self._load_settings())
        except: #TODO: what goes here? file not found?
            logging.debug("Failed to load region set settings")
        self._persistent_data.update(kwargs)
        self.bounds = self._find_bounds()
            
    def _get_name(self, path):
        """Get the actual name of a world from the level.dat file
        """
        levelnbt = nbt.load(self.get_level_path())
        try:
            name = levelnbt[0]['Data']['LevelName']
        except (IndexError, KeyError):
            #assume levelname is missing
            name = "world"
        return name

    def _get_pickle_filename(self):
        """
        """
        #TODO this should actually pull from the output dir but we don't know
        #  about it yet.
        return os.path.join(self.path, self.SETTINGS_FILE)
        
    def _read_settings(self):
        #read data from pickle file into self._persistent_data
        #TODO: merge or overwrite?
        settings = {}
        pickle_filename = self._get_pickle_filename()
        if os.path.exists(pickle_filename):
            with open(pickle_filename, 'rb') as pickle_file:
                settings = cPickle.load(pickle_file)
        return settings
        
    def write_settings(self):
        #write self._persistent_data to pickle file
        pass
    
    def biome_data_available(self):
        """Check if any biome data is available
        """
        return len(glob.glob(os.join(self.world.path, self.BIOME_DIR_NAME,
            self.BIOME_FILENAME_TPL.replace('%d', '*'))) > 0

    def _get_biome_data_path(self, regionX, regionY):
        """
        """
        return os.path.join(self.world.path, self.BIOME_DIR_NAME,
            self.BIOME_FILENAME_TPL % (regionX, regionY))

    def get_biome_data(self, chunkX, chunkY):
        """
        """
        pass

    def get_region_paths(self):
        return glob.glob(os.path.join(
            self.path, self.REGION_FILENAME_TPL.replace('%d', '*'))
    
    def get_region_path(self, chunkX, chunkY):
        """
        """
        return os.join(self.path,
            self.REGION_FILENAME_TPL %
                (chunkX//32, chunkY//32, self.REGION_FILE_EXT))
    
    def get_chunk(self, chunkX, chunkY):
        """
        """
        #TODO this replaces World.load_from_region
        return None
        
    def reload_region(self, regionX, regionY):
        """
        """
        #TODO replaces World.reload_region
        
    def get_spawn_point(self):
        """Get the spawn point from level.dat, this not necessarily where
        the player marker will be placed and will likely differ slightly from
        where players actually spawn.
        """
        #TODO implement this
        return (0,0,0)
        
    def get_spawn_POI(self):
        """Get the point where players are actually likely to spawn and where
        the spawn marker should be placed.
        """
        #TODO replaces World.findTrueSpawn
        return self.get_spawn_point()
        
    def _find_bounds(self):
        """
        """
        #TODO this probably replaces World.go which is a stupid name
        #also, figure out how to handle regionlist
        minX = maxX = minY = maxY = 0
        for regionX, regionY in self._region_file_iterator():
            minX = min(minX, regionX)
            maxX = max(maxX, regionX)
            minY = min(minY, regionY)
            maxY = max(maxY, regionY)
        if sum(map(abs, [minX, maxX, minY, maxY])) is 0:
            logging.error("No regions found")
            #TODO handle this better
            raise Exception("exit 1")
        else:
            
    
    def get_id_hash(self):
        """Get a hash representing a set config parameters. If this doesn't
        match the hash in the output dir then we should probably require
        force render so people don't get maps with a grabbag set of tiles.
        """
        #TODO: this is almost guaranteed to be wrong, fix it
        #is probably also not needed
        return mhash.sha1(repr(self._persistent_data))
        
    def _region_file_iterator(self, region_paths=None):
        """Iterates over region filenames in the set returning their coords
        """
        #TODO add some validation
        temp = 0
        for region_filename in map(os.path.basename,
                self.get_region_paths() if region_paths is None else region_paths)
            regionX, regionY = map(int, region_filename.split('.')[1:3])
            #TODO refactor this into a north_transform method
            if self._config['north_directon'] == 'upper-left':
                temp = regionX
                regionX = -regionY - 1
                regionY = temp
            elif self._config['north_directon'] == 'upper-right':
                regionX = -regionX - 1
                regionY = -regionY - 1
            elif self._config['north_directon'] == 'lower-right':
                temp = regionX
                regionX = regionY
                regionY = -temp - 1
            yield (regionX, regionY)
