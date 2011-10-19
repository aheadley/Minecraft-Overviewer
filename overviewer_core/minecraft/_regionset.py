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

class RegionSet(object):
    """Represents the set of region files that make up a single dimension in a
    world.
    """
    
    #TODO persistent data stuff really belongs to the quadtree and should be
    #  moved there at some point
    REGION_FILENAME_TPL         = 'r.%d.%d.mcr'
    REGION_DATA_CACHE_LIMIT     = 256
    EMPTY_CHUNK                 = [None, None]
    DEFAULT_DATA                = {
        'north_direction': 'lower-left',
    }
    NORTH_ROTATIONS             = {
        'lower-left': 0,
        'upper-left': 1,
        'upper-right': 2,
        'lower-right': 3,
    }

    #this may make alternate chunk/region sizes easier to deal with in the future
    #TODO actually change stuff to use these. though they should probably go somewhere else
    _CHUNK_WIDTH                = 16
    _CHUNK_HEIGHT               = 16
    _CHUNK_DEPTH                = 128
    _REGION_WIDTH               = 32
    _REGION_HEIGHT              = 32
    
    def __init__(self, world, name, **kwargs):
        self.world = world
        self.name = name
        self.path = os.path.join(
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
        self.bounds = self._find_bounds()
        self._region_cache = {}
            
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
            
    def get_region_coords_from_chunk(self, chunkX, chunkY):
        """Convert chunk coords into the containing region coords
        """
        return chunkX//32, chunkY//32
    
    def get_region_path_from_chunk(self, chunkX, chunkY):
        """
        """
        return os.path.join(self.path, self.get_region_filename_from_chunk(
            chunkX, chunkY))
        
    def get_region_filename_from_chunk(self, chunkX, chunkY):
        """
        """
        region_coords = self.get_region_coords_from_chunk(chunkX, chunkY)
        return self.get_region_filename(region_coords[0], region_coords[1])
        
    def get_region_path(self, regionX, regionY):
        """
        """
        return os.path.join(self.path, self.get_region_filename(regionX, regionY))
    
    def get_region_filename(self, regionX, regionY):
        """
        """
        return self.REGION_FILENAME_TPL % (regionX, regionY)
    
    def get_chunk_relative(self, regionX, regionY, chunkX, chunkY):
        """Get the (properly rotated) chunk data from a chunk by it's coords
        relative to the region it's contained in
        """
        #TODO this needs to be looked over, i suspect it is doing some silly things
        # also, chunkX and chunkY should be constrained to [0, 32)
        # this should probably tie into get_region as well
        # this is probably almost completely unneccesary in light of the new get_region
        
        region_coords = (regionX, regionY)
        chunk_coords = (chunkX, chunkY)
        if chunk_coords not in self._region_cache[region_coords][2]:
            try:
                chunk_data = self.get_region(*region_coords).load_chunk(chunkX, chunkY).read_all()
            except AttributeError:
                self._region_cache[region_coords][2][chunk_coords] = self.EMPTY_CHUNK
            else:
                north_rotations = self.get_north_rotations(
                    self._config['north_direction'])
                level = chunk_data[1]['Level']
                cache_data = level
                cache_data['Blocks']
                cache_data['Blocks'] = numpy.array(numpy.rot90(
                    numpy.frombuffer(level['Blocks'], dtype=numpy.uint8).reshape((16,16,128)),
                        north_rotations))
                cache_data['Data'] = numpy.array(numpy.rot90(
                    numpy.frombuffer(level['Data'], dtype=numpy.uint8).reshape((16,16,64)),
                        north_rotations))
                cache_data['SkyLight'] = numpy.array(numpy.rot90(
                    numpy.frombuffer(level['SkyLight'], dtype=numpy.uint8).reshape((16,16,64)),
                        north_rotations))
                cache_data['BlockLight'] = numpy.array(numpy.rot90(
                    numpy.frombuffer(level['BlockLight'], dtype=numpy.uint8).reshape((16,16,64)),
                        north_rotations()))
                self._region_cache[region_coords][2][chunk_coords] = cache_data
        return self._region_cache[region_coords][2][chunk_coords]
    
    def get_chunk_absolute(self, chunkX, chunkY):
        """Get the chunk data for a chunk by it's absolute coords
        """
        region_coords = self.get_region_coords_from_chunk(chunkX, chunkY)
        return self.get_chunk_relative(region_coords[0], region_coords[1],
            chunkX % 32, chunkY % 32)
    
    #TODO use LRU decorator here? how to skip cache then?
    def get_region(self, regionX, regionY, bypass_cache=False):
        """
        """
        #TODO replaces World.reload_region
        coords = (regionX, regionY)
        if bypass_cache or coords not in self._region_cache:
            if len(self._region_cache) > self.REGION_DATA_CACHE_LIMIT:
                #TODO trim cache
                pass
            if bypass_cache and coords in self._region_cache:
                self._region_cache[coords][0].closefile()
                del self._region_cache[coords]
                #need to clear chunk cache as well
            #load into cache
            region = nbt.MCRFileReader(
                self.get_region_path(*coords), self._config['north_direction'])
            region_mtime = None
            region_chunk_cache = {}
            #should biome data be in this?
            self._region_cache[coords] = (region, region_mtime, region_chunk_cache)
        return self._region_cache[coords]
        
    def get_region_data(self, regionX, regionY):
        """
        """
        return self.get_region(regionX, regionY)[0]
        
    def get_region_mtime(self, regionX, regionY):
        """
        """
        return self.get_region(regionX, regionY)[1]
        
    def get_region_chunks(self, regionX, regionY):
        """
        """
        return self.get_region(regionX, regionY)[2]
        
    def get_spawn_POI(self):
        """Get the point where players are actually likely to spawn and where
        the spawn marker should be placed.
        """
        #TODO replaces World.findTrueSpawn
        return self.world.get_spawn_point()
        
    def get_north_rotations(self, direction):
        """Translate a north direction into the rotations needed
        """
        #TODO verify default is what it should be
        return self.NORTH_ROTATIONS.get(direction, 1)
        
    #TODO these should probably be class methods
    def get_diag_coords_from_chunk(self, chunkX, chunkY):
        """Takes a coordinate (chunkx, chunky) where chunkx and chunky are
        in the chunk coordinate system, and figures out the row and column
        in the image each one should be. Returns (col, row).
        """
        # columns are determined by the sum of the chunk coords, rows are the
        # difference
        return chunkX + chunkY, chunkY - chunkX
    
    def get_chunk_coords_from_diag(self, column, row):
        """Inverse of get_diag_coords_from_chunk()
        """
        return (column - row) / 2, (column + row) / 2
        
    def _find_bounds(self):
        """Find the min/max of the x,y of chunks in the region set
        
        Note that these chunks may not actually exists, only that there is at
        least one region that could contain a chunk at these values.
        """
        #TODO this probably replaces World.go which is a stupid name
        #also, figure out how to handle regionlist
        #also, maybe faster to 
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
        min_chunkX = minX * 32
        max_chunkX = maxX * 32 + 32
        min_chunkY = minY * 32
        max_chunkY = maxY * 32 + 32
        
        min_column = max_column = min_row = max_row = 0
        for chunkX, chunkY in [(minX, minY), (minX, maxY), (maxX, minY), (maxX, maxY)]:
            column, row = self.get_diag_coords_from_chunk(chunkX, chunkY)
            min_column = min(min_column, column)
            max_column = max(max_column, column)
            min_row = min(min_row, row)
            max_row = max(max_row, row)
        return {
            min_column=min_column,
            max_column=max_column,
            min_row=min_row,
            max_row=min_row,
        }
    
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
