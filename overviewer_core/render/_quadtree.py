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

import multiprocessing
import itertools
import os
import os.path
import functools
import re
import shutil
import collections
import json
import logging
#TODO not sure this is right
from .. import util
import cPickle
import stat
import errno 
import time
from time import gmtime, strftime, sleep

from PIL import Image

from ..minecraft import nbt
from .. import render
from ..render.c_overviewer import get_render_mode_inheritance
from ..render import optimize_image


"""
This module has routines related to generating a quadtree of tiles

"""

class QuadTreeGenerator(object):
    """
    """
    
    PERSISTENT_DATA_FILENAME    = 'overviewer.dat'
    """TODO doc this, tl;dr is this is the maximum zoom that can ever be required
    
    chunk coords are signed 32bit int, so range is
    -2^32 <-> 2^32-1 which means the farthest chunk is at -2^32, -2^32 which
    requires zoom level 33 (see RegionSet.get_diag_coords_from_chunk)
    """
    MAX_TREE_DEPTH              = 33
    WARN_TREE_DEPTH             = self.MAX_TREE_DEPTH // 2
    #TODO these should probably be module constants/globals/whatever
    TILE_SIZE                   = 384
    HALF_TILE_SIZE              = self.TILE_SIZE // 2
    QTR_TILE_SIZE               = self.TILE_SIZE // 4
    TILE_IMG_FORMATS            = ('jpg', 'png')

    @staticmethod
    def iterate_base4(d):
        """Iterates over a base 4 number with d digits
        """
        return itertools.product(xrange(4), repeat=d)

    def __init__(self, region_set, dest_path, **kwargs):
        """Generates a quadtree from the world given into the given destination
        directory

        If depth is given, it overrides the calculated value. Otherwise, the
        minimum depth that contains all chunks is calculated and used.
        """
        self.region_set = region_set
        self.dest_path = dest_path
        self._depth = kwargs.get('depth', None)
        #Used by rendernode to keep track of quadtrees
        self._render_index = None
        if self._depth is None:
            #we didn't get a depth so we need to figure it out
            for tree_depth in xrange(self.MAX_TREE_DEPTH):
                # Will 2^tree_depth tiles wide and high suffice?
                # X has twice as many chunks as tiles, then halved since this is a
                # radius
                radiusX = 2 ** tree_depth
                # Y has 4 times as many chunks as tiles, then halved since this is
                # a radius
                radiusY = 2 * 2 ** tree_depth
                if  radiusX >= self.region_set.bounds['max_column'] and \
                    -radiusX <= self.region_set.bounds['min_column'] and \
                    radiusY >= self.region_set.bounds['max_row'] and \
                    -radiusY <= self.region_set.bounds['min_row']:
                    break
            else:
                logging.error("Your map is waaaay too big! Use the 'zoom' \
option in 'settings.py'.")
                raise ValueError("Tree depth limit reached while trying to fit map")
            self._depth = tree_depth
        else:
            radiusX = 2 ** self._depth
            radiusY = 2 * 2 ** self._depth

        self._persistent_data = self.DEFAULT_DATA
        try:
            self._persistent_data.update(self._read_persistent_data())
        except: #TODO: what goes here? file not found?
            logging.debug("Failed to load region set settings")
        #TODO this doesn't handle north_direction conflicts at all
        self._persistent_data.update(kwargs)
    
    def pre_process(self):
        """Process the tile directory tree before we render
        """
        current_depth = self._get_current_depth()
        if current_depth is not None and current_depth is not self._depth:
            logging.warning("Your map has changed size, re-arranging tiles...")
            if self._depth > current_depth:
                logging.warning("Expansion detected, increasing tree depth...")
                for _ in xrange(self._depth - current_depth):
                    self._increase_depth()
            elif self._depth < current_depth:
                logging.warning("Shrinkage detected, decreasing tree depth...")
                for _ in xrange(current_depth - self._depth):
                    self._decrease_depth()
    
    def iterate_world_tiles(self):
        """An iterator for the tiles at the lowest (most detailed) layer. These
        are the tiles that are generated from scratch instead of stiched together.
        """
        #replaces QuadtreeGen.get_worldtiles
        for path in self.iterate_base4(self._depth):
            column_start, row_start = self._get_chunk_coords_by_path(path)
            column_end = column_start + 2
            row_end = row_start + 4
            #we pass the path around as a string to save memory
            tile_path = os.path.join(map(str, path))
            yield [self._render_index, column_start, column_end, row_start,
                row_end, tile_path]
    
    def iterate_composed_tiles(self, level):
        """An iterator for all but the lowest level of tiles. These are the tiles
        that are stiched together from the lowest level of tiles.
        """
        #replaces QuadtreeGen.get_innertiles
        #TODO should check that level != self._depth ?
        for path in self.iterate_base4(level):
            yield [self._render_index, os.path.join(map(str, path))]

    def get_depth(self):
        """
        """
        return self._depth
    
    def render_composed_tile(self, path, force=False):
        """Renders a tile at os.path.join(dest, name)+".ext" by taking tiles
        from os.path.join(dest, name, "{0,1,2,3}.png")
        """
        #replaces QuadtreeGen.render_innertile
        img_format = self._persistent_data['img_format']
        if path is not None:
            img_path = os.path.join(self.dest_path, '%s.%s' % (path, img_format))
        else:
            #base image
            img_path = os.path.join(self.dest_path, 'base.' + img_format)
        target_dirname = os.path.dirname(img_path)
        quad_img_paths = [
            [(0, 0),
                os.path.join(target_dirname, '0.' + img_format)],
            [(self.HALF_TILE_SIZE, 0),
                os.path.join(target_dirname, '1.' + img_format)],
            [(0, self.HALF_TILE_SIZE),
                os.path.join(target_dirname, '2.' + img_format)],
            [(self.HALF_TILE_SIZE, self.HALF_TILE_SIZE),
                os.path.join(target_dirname, '3.' + img_format)],
        ]
        #stat the tile, we need to know if it exists or it's mtime
        try:
            img_mtime =  os.stat(img_path)[stat.ST_MTIME];
        except OSError, e:
            if e.errno != errno.ENOENT:
                raise
            img_mtime = None

        #check mtimes on each part of the quad, this also checks if they exist
        rerender = force or img_mtime is None
        quad_img_paths_filtered = []
        for quad_img_path in quad_img_paths:
            try:
                quad_img_mtime = os.stat(quad_img_path[1])[stat.ST_MTIME];
                quad_img_paths_filtered.append(quad_img_path)
                if quad_img_mtime > img_mtime:
                    rerender = True
            except OSError:
                # We need to stat all the quad files, so keep looping
                pass
            
        if not quad_img_paths_filtered:
            # none of the child images exist so this tile shouldn't either
            if img_mtime is not None:
                os.unlink(img_path)
            return
        elif not rerender:
            # quit now if we don't need rerender
            return
        else:
            # Create the actual image now
            img = Image.new('RGBA', (self.TILE_SIZE, self.TILE_SIZE),
                self._persistent_data['bg_color'])

            # we'll use paste (NOT alpha_over) for quadtree generation because
            # this is just straight image stitching, not alpha blending
            for quad_path in quad_img_paths_filtered:
                try:
                    quad_img = Image.open(quad_path[1]).resize(
                        (self.HALF_TILE_SIZE, self.HALF_TILE_SIZE), Image.ANTIALIAS)
                    img.paste(quad_img, quad_path[0])
                #TODO better exception here
                except Exception, e:
                    logging.warning("Couldn't open %s. It may be corrupt, you \
may need to delete it. %s", quad_path[1], e)

            # Save it
            self._img_save(img, img_path)
            #TODO post tile render hook here
    
    def render_world_tile(self, column_start, column_end, row_start, row_end,
        path, force=False):
        """Renders just the specified chunks into a tile and save it. Unlike usual
        python conventions, rowend and colend are inclusive. Additionally, the
        chunks around the edges are half-way cut off (so that neighboring tiles
        will render the other half)

        chunks is a list of (col, row, chunkx, chunky, filename) of chunk
        images that are relevant to this call (with their associated regions)

        The image is saved to path+"."+self.imgformat

        If there are no chunks, this tile is not saved (if it already exists, it is
        deleted)

        Standard tile size has colend-colstart=2 and rowend-rowstart=4

        There is no return value
        # width of one chunk is 384. Each column is half a chunk wide. The total
        # width is (384 + 192*(numcols-1)) since the first column contributes full
        # width, and each additional one contributes half since they're staggered.
        # However, since we want to cut off half a chunk at each end (384 less
        # pixels) and since (colend - colstart + 1) is the number of columns
        # inclusive, the equation simplifies to:
        # The standard tile size is 3 columns by 5 rows, which works out to 384x384
        # pixels for 8 total chunks. (Since the chunks are staggered but the grid
        # is not, some grid coordinates do not address chunks) The two chunks on
        # the middle column are shown in full, the two chunks in the middle row are
        # half cut off, and the four remaining chunks are one quarter shown.
        # The above example with cols 0-3 and rows 0-4 has the chunks arranged like this:
        #   0,0         2,0
        #         1,1
        #   0,2         2,2
        #         1,3
        #   0,4         2,4

        # Due to how the tiles fit together, we may need to render chunks way above
        # this (since very few chunks actually touch the top of the sky, some tiles
        # way above this one are possibly visible in this tile). Render them
        # anyways just in case). "chunks" should include up to rowstart-16
        """
        #replaces QuadtreeGen.render_worldtile

        img_width = self.HALF_TILE_SIZE * (column_end - column_start)
        img_height = self.HALF_TILE_SIZE * (row_end - row_start)
        img_path = os.path.join(self.dest_path, '%s.%s' %
            (path, self._persistent_data['img_format']))
        img_dirname = os.path.dirname(img_path)
        chunks = self.get_chunks_in_range(column_start, column_end, row_start,
            row_end)

        #stat the file, we need to know if it exists or it's mtime
        try:
            img_mtime =  os.stat(img_path)[stat.ST_MTIME];
        except OSError, e:
            if e.errno != errno.ENOENT:
                raise
            img_mtime = None

        if not chunks:
            # No chunks were found in this tile
            if img_mtime is not None:
                os.unlink(img_path)
            return

        try:
            os.makedirs(img_dirname)
        except OSError, e:
            # Ignore errno EEXIST: file exists. Since this is multithreaded,
            # two processes could conceivably try and create the same directory
            # at the same time.
            if e.errno != errno.EEXIST:
                raise

        # check chunk mtimes to see if they are newer
        rerender = force
        if not rerender:
            for column, row, chunkX, chunkY in chunks:
                region_coords = self.region_set.get_region_coords_from_chunk(
                    chunkX, chunkY)
                try:
                    region_data = self.region_set.get_region(*region_coords)
                except OSError:
                    continue
                # don't even check if it's not in the regionlist
                if  self.region_list and \
                    self.region_set.get_region_filename(*region_coords) \
                        not in self.region_list:
                    continue

                # check region file mtime first.
                if region_data[1] <= img_mtime:
                    continue

                if region_data[0].get_chunk_timestamp(chunkX, chunkY) > img_mtime:
                    rerender = True
                    break

        if not rerender:
            return
            
        # Compile this image
        img = Image.new('RGBA', (img_width, img_height),
            self._persistent_data['bg_color'])

        rendermode = self.rendermode
        # col colstart will get drawn on the image starting at x coordinates -(384/2)
        # row rowstart will get drawn on the image starting at y coordinates -(192/2)
        for column, row, chunkX, chunkY in chunks:
            posX = -self.HALF_TILE_SIZE + (column - column_start) * self.HALF_TILE_SIZE
            posY = -self.QTR_TILE_SIZE + (row - row_start) * self.QTR_TILE_SIZE
            # draw the chunk!
            try:
                renderer = chunk.ChunkRenderer((chunkX, chunkY), self.region_set,
                    render_mode)
                renderer.chunk_render(img, posX, posY, None)
            except chunk.ChunkCorrupt:
                # an error was already printed
                #TODO stick warning sign in instead of chunk image maybe?
                pass

        # Save them
        self._img_save(img, img_path)
        #TODO post tile render hook here

    def _get_persistent_data_path(self):
        """
        """
        return os.path.join(self.dest_path, self.PERSISTENT_DATA_FILENAME)
    
    def _read_persistent_data(self):
        """Read persistent data from backing storage if available
        """
        data = {}
        pd_path = self._get_persistent_data_path()
        with open(pd_path, 'rb') as pd_file:
            data = cPickle.load(pd_file)
        return data
        
    def _write_persistent_data(self, data):
        """Write the persistent data to backing storage.
        """
        pd_path = self._get_persistent_data_path()
        with open(pd_path + '.new', 'wb') as pd_file:
            cPickle.dump(data, pd_file)
        try:
            # Renames are not atomic on Windows and throw errors if the
            #   destination already exists so we have to remove it first.
            os.remove(pd_path)
        except OSError:
            #TODO better exception here
            os.remove(pd_path + '.new')
            raise Exception("can't write new pd_file")
        else:
            os.rename(pd_path + '.new', pd_path)
    
    def _get_current_depth(self):
        """
        """
        return self._persistent_data['tree_depth']
    
    def _increase_depth(self):
        """Moves existing tiles into place for a larger tree
        """
        get_path = functools.partial(os.path.join, self.dest_path)

        # At top level of the tree:
        # quadrant 0 is now 0/3
        # 1 is now 1/2
        # 2 is now 2/1
        # 3 is now 3/0
        # then all that needs to be done is to regenerate the new top level
        for i in range(4):
            new_i = (3,2,1,0)[i]
            new_dirname = 'new' + str(i)
            new_dirpath = get_path(new_dirname)
            filenames = ['%d.%s' % (i, self._persistent_data['img_format'], str(i)]
            new_filenames = ['%d.%s' % (new_i, self._persistent_data['img_format'], str(new_i)]
            
            os.mkdir(new_dirpath)
            for filename, new_filename in zip(filenames, new_filenames):
                file_path = get_path(filename)
                if os.path.exists(file_path):
                    os.rename(file_path, get_path(new_dirname, new_filename))
            os.rename(new_dirpath, get_path(str(i)))
    
    def _decrease_depth(self):
        """If the map size decreases, or perhaps the user has a depth override
        in effect, re-arrange existing tiles for a smaller tree
        """
        get_path = functools.partial(os.path.join, self.dest_path)

        # quadrant 0/3 goes to 0
        # 1/2 goes to 1
        # 2/1 goes to 2
        # 3/0 goes to 3
        # Just worry about the directories here, the files at the top two
        # levels are cheap enough to replace
        if os.path.exists(get_path('0', '3')):
            os.rename(get_path('0', '3'), get_path('new0'))
            shutil.rmtree(get_path('0'))
            os.rename(get_path('new0'), get_path('0'))

        if os.path.exists(get_path('1', '2')):
            os.rename(get_path('1', '2'), get_path('new1'))
            shutil.rmtree(get_path('1'))
            os.rename(get_path('new1'), get_path('1'))

        if os.path.exists(get_path('2', '1')):
            os.rename(get_path('2', '1'), get_path('new2'))
            shutil.rmtree(get_path('2'))
            os.rename(get_path('new2'), get_path('2'))

        if os.path.exists(get_path('3', '0')):
            os.rename(get_path('3', '0'), get_path('new3'))
            shutil.rmtree(get_path('3'))
            os.rename(get_path('new3'), get_path('3'))
    
    def _get_chunks_in_range_diag(self, column_start, column_end, row_start, row_end):
        """
        """
        #replaces QuadtreeGen.get_chunks_in_range
        chunk_list = []
        get_chunk_coords = self.region_set.get_chunk_coords_from_diag
        get_region_coords = self.region_set.get_region_coords_from_chunk
        get_region = self.region_set.get_region
        get_chunk = self.region_set.get_chunk_absolute
        regionX = regionY = chunk = region_data = None
        
        for row in xrange(row_start - 16, row_end + 1):
            for column in xrange(column_start, column_end + 1):
                # due to how chunks are arranged, we can only allow
                # even row, even column or odd row, odd column
                # otherwise, you end up with duplicates!
                if row % 2 is not column % 3:
                    continue
                else:
                    chunkX, chunkY = get_chunk_coords(column, row)
                    #TODO this doesn't really handle chunks that don't exist
                    chunk_list.append((column, row, chunkX, chunkY,
                        get_chunk(chunkX, chunkY)))
        return chunk_list

    #TODO this method's name is probably not very accurate
    def _get_chunk_coords_by_path(self, path):
        """Get the x,y chunk coords of a tile
        """
        max_bounds = self._get_bounds_by_depth(self._depth)
        x = max_bounds['min_column']
        y = max_bounds['min_row']
        sizeX = max_bounds['max_column']
        sizeY = max_bounds['max_row']
        
        for branch in path:
            if branch in (1,3):
                x += sizeX
            if branch in (2,3):
                y += sizeY
            sizeX //= 2
            sizeY //= 2
        
        return x, y
    
    def _get_bounds_by_depth(self, depth):
        """
        """
        return {
            'min_column': -2 ** depth,
            'max_column': 2 ** depth,
            'min_row':    -2 * 2 ** depth,
            'max_row':    2 * 2 ** depth,
        }
    def _save_image(img, img_path):
        """
        """
        if self._persistent_data['img_format'] == 'jpg':
            img.save(img_path,
                quality=self._persistent_data['img_quality'],
                subsampling=self.JPG_SUBSAMPLING)
        else:
            img.save(img_path)
    
