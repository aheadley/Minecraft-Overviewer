def base36encode(number, alphabet='0123456789abcdefghijklmnopqrstuvwxyz'):
    """Convert an integer to a base36 string.
    """
    if not isinstance(number, (int, long)):
        raise TypeError('Number must be an integer: %s' % repr(number))
    
    new_number = abs(number)
    base36 = ''
    # Special case for zero
    if number == 0:
        base36 = '0'
    else:
        while new_number != 0:
            new_number, i = divmod(new_number, len(alphabet))
            base36 = alphabet[i] + base36

        if number < 0:
            base36 = "-" + base36
    return base36

class RegionSet(object):
    """Represents a set of region files that make up a world/dimension
    """
    
    SETTINGS_FILE   = 'overviewer.dat'
    #these should probably be filename templates
    BIOME_FILE_EXT  = 'biome'
    REGION_FILE_EXT = 'mcr'
    
    REGION_FILE_LIMIT   = 256
    #TODO i don't even know what these are used for
    CHUNK_X_LIMIT       = 1024
    
    def __init__(self, world, path, **kwargs):
        self.world = world
        self.name = self._get_name(path)
        self.path = os.join(self.world.path, path)
        self._config = kwargs
        try:
            self._load_settings()
        except: #TODO: what goes here? file not found?
            #print log message
        else:
            #TODO: this needs a conditional on force render
            self._config = kwargs
            
    def _get_name(self, path):
        """Get the actual name of a world from the level.dat file
        """
        #read name from level.dat
        return 'world'
        
    def _load_settings(self):
        #read data from pickle file into self._config
        #TODO: merge or overwrite?
        return
        
    def save_settings(self):
        #write self._config to pickle file
        return
    
    def biome_data_available(self):
        return len(glob.glob(os.join(self.path,'*.{0}' % self.BIOME_FILE_EXT))) > 0
    
    def get_region_path(self, chunkX, chunkY):
        """
        """
        return os.join(self.path,
            'r.%i.%i.%s' % (chunkX//32, chunkY//32, self.REGION_FILE_EXT))
    
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
    
    def get_id_hash(self):
        """Get a hash representing a set config parameters. If this doesn't
        match the hash in the output dir then we should probably require
        force render so people don't get maps with a grabbag set of tiles.
        """
        #TODO: this is almost guaranteed to be wrong, fix it
        return mhash.sha1(repr(self._config))
        
    def _get_region_file_iterator(self):
        """
        """
        #TODO replaces World._iterate_regionfiles
        yield (0,0)