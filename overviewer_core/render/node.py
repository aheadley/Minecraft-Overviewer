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
import Queue
import itertools
from itertools import cycle, islice
import os
import os.path
import functools
import re
import shutil
import collections
import json
import logging
from .. import util
import textures
import c_overviewer
import cPickle
import stat
import errno 
import time
from time import gmtime, strftime, sleep
import traceback


"""
This module has routines related to distributing the render job to multiple nodes

"""

def catch_keyboardinterrupt(func):
    """Decorator that catches a keyboardinterrupt and raises a real exception
    so that multiprocessing will propagate it properly
    """
    @functools.wraps(func)
    def wrapped_func(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            logging.error("Ctrl-C caught!")
            #TODO this should do something else probably
            raise Exception("Exiting")
        except:
            traceback.print_exc()
            raise
    return wrapped_func
    
CHILD_RENDERNODE = None
def pool_initializer(rendernode):
    """
    """
    logging.debug("Child process {0}".format(os.getpid()))
    #stash the quadtree objects in a global variable after fork() for windows compat.
    global CHILD_RENDERNODE
    CHILD_RENDERNODE = rendernode
    
    # make sure textures are generated for this process
    # and initialize c_overviewer
    textures.generate(path=rendernode.options.get('textures_path', None),
            north_direction=rendernode.options.get('north_direction', None))
    c_overviewer.init_chunk_render()
    
    # setup c_overviewer rendermode customs / options
    for mode in rendernode.options.custom_rendermodes:
        c_overviewer.add_custom_render_mode(mode, rendernode.options.custom_rendermodes[mode])
    for mode in rendernode.options.rendermode_options:
        c_overviewer.set_render_mode_options(mode, rendernode.options.rendermode_options[mode])
    
    # load biome data in each process, if needed
    for quadtree in rendernode.quadtrees:
        if quadtree.region_set.useBiomeData:
            # make sure we've at least *tried* to load the color arrays in this process...
            textures.prepareBiomeData(quadtree.region_set.world.path)
            if not textures.grasscolor or not textures.foliagecolor:
                raise Exception("Can't find grasscolor.png or foliagecolor.png")
            # only load biome data once
            #TODO this will need to change since different worlds can have
            #  different biome data
            break
                    
def roundrobin(iterables):
    """Round robin pattern iterator

    roundrobin('ABC', 'D', 'EF') --> A D E B F C

    http://docs.python.org/library/itertools.html
    Recipe credited to George Sakkis
    """
    pending = len(iterables)
    nexts = cycle(iter(it).next for it in iterables)
    while pending:
        try:
            for next in nexts:
                yield next()
        except StopIteration:
            pending -= 1
            nexts = cycle(islice(nexts, pending))

            
class RenderNode(object):
    """Distributes the rendering of a list of quadtrees.
    """

    RESULT_DRAIN_MARK           = 10000
    #minimum time in seconds between queue drains
    RESULT_DRAIN_INTERVAL       = 1
    
    def __init__(self, quadtrees, options):
        """Distributes the rendering of a list of quadtrees.
        """

        if not len(quadtrees):
            raise ValueError("there must be at least one quadtree to work on")    

        self.options = options
        self.quadtrees = quadtrees
        #List of changed tiles
        self.rendered_tiles = []

        #bind an index value to the quadtree so we can find it again
        #and figure out which worlds are where
        i = 0
        self.region_sets = []
        for qt in quadtrees:
            qt._render_index = i
            i += 1
            if qt.region_set not in self.region_sets:
                self.worlds.append(q.world)

        manager = multiprocessing.Manager() 
        # queue for receiving interesting events from the renderer
        # (like the discovery of signs!
        #stash into the world object like we stash an index into the quadtree
        for region_set in self.region_sets:
            region_set.poi_queue = manager.Queue()


    def print_statusline(self, finished_tiles, total_tiles, level, total_levels,
            force=False):
        if  force \
            or (complete < 100 and complete % 25 is 0) \
            or (complete < 1000 and complete % 100 is 0) \
            or (complete % 1000 is 0):
            logging.info("{0}/{1} ({4}%) tiles complete on level {2}/{3}".format(
                finished_tiles, total_tiles, level, total_levels,
                '%.1f' % ((100.0 * complete) / total))
                
    def process_batches(self, worker_count):
        """Renders all tiles
        """
        
        logging.debug("Parent process {0}".format(os.getpid()))
        # Create a pool
        if worker_count is 1:
            worker_pool = FakePool()
            pool_initializer(self)
        else:
            pool_initializer(self)
            worker_pool = multiprocessing.Pool(
                processes=worker_count,
                initializer=pool_initializer,
                initargs=(self,))
            #warm up the pool so it reports all the worker id's
            if logging.getLogger().level >= 10:
                worker_pool.map(bool,xrange(multiprocessing.cpu_count()),1)
            else:
                worker_pool.map_async(bool,xrange(multiprocessing.cpu_count()),1)
        logging.debug("Warmed up worker pool with {0} workers".format(worker_count))
                
        # do per-quadtree init
        deepest_zoom = 0
        total_predicted_tile_count = 0
        for qt in self.quadtrees:
            total_predicted_tile_count += 4 ** qt.get_depth()
            deepest_zoom = max(deepest_zoom, qt.get_depth())

        results = collections.deque()
        logging.info("There are {2} layer{3}, {0} tiles, and {1} levels to render".format(
            len(self.quadtrees), 's' if len(quadtrees) > 1 else '',
            total_predicted_tile_count, deepest_zoom))
        logging.info("Don't worry, each level has 25% as many tiles as \
the last and the first takes extra time")
        for level in xrange(deepest_zoom, 0, -1):
            if level is deepest_zoom:
                tile_render_method = self._apply_render_world_tiles
                poi_method = self._drain_poi_queue
            else:
                tile_render_method = self._apply_render_composed_tiles
                #composed tiles don't have POIs
                poi_method = None
            logging.info("Starting level {0}".format(level))
            self._process_results(results, worker_pool, tile_render_method,
                level, poi_method)
            logging.info("Finished level {0}".format(level))

        pool.close()
        pool.join()

        # Do the final one right here:
        for qt in quadtrees:
            qt.render_composed_tile(None)

    def _apply_render_world_tiles(self, pool, batch_size, zoom):
        """Returns an iterator over result objects. Each time a new result is
        requested, a new task is added to the pool and a result returned.

        Note that the zoom arg is completely ignored and only for compat with
        _apply_render_compose_tiles
        """
        batch = []
        jobcount = 0       
        # roundrobin add tiles to a batch job (thus they should all roughly
        #   work on similar chunks)
        iterators = [qt.iterate_world_tiles() for qt in self.quadtrees]
        for job in roundrobin(iterators):
            # fixup so the worker knows which quadtree this is
            job[0] = job[0]._render_index
            # Put this in the batch to be submited to the pool
            batch.append(job)
            jobcount += 1
            if jobcount >= batch_size:
                yield pool.apply_async(
                    func=batch_render_world_tiles,
                    args=[batch])
                jobcount = 0
                batch = []
        if jobcount > 0:
            yield pool.apply_async(
                func=batch_render_world_tiles,
                args=[batch])

    def _apply_render_composed_tiles(self, pool, batch_size, zoom):
        """Same as _apply_render_worltiles but for the inntertile routine.
        Returns an iterator that yields result objects from tasks that have
        been applied to the pool.
        """
        batch = []
        jobcount = 0
        # roundrobin add tiles to a batch job (thus they should all roughly work
        #  on similar chunks)
        iterators = [qt.iterate_composed_tiles(zoom) for qt in self.quadtrees \
            if zoom <= qt.get_depth()]
        for job in roundrobin(iterators):
            # fixup so the worker knows which quadtree this is  
            job[0] = job[0]._render_index
            # Put this in the batch to be submited to the pool  
            batch.append(job)
            jobcount += 1
            if jobcount >= batch_size:
                jobcount = 0
                yield pool.apply_async(
                    func=batch_render_composed_tiles,
                    args=[batch])
                batch = []
        if jobcount > 0:
            yield pool.apply_async(
                func=batch_render_composed_tiles,
                args=[batch])

    def _get_batch_size(self):
        size = 4 * len(self.quadtrees)
        while size < 10:
            size *= 2
        return size

    def _process_results(self, results, worker_pool, render_method,
            level, poi_method=None):
        """
        """
        assert len(results) is 0
        batch_size = self._get_batch_size()
        finished_tile_count = 0
        total_tile_count = 4 ** level
        old_timestamp = time.time()
        for batch_result in render_method(worker_pool, batch_size, level):
            results.append(batch_result)
            # every second drain some of the queue
            #TODO seems like there should be a better way to decide to drain the
            #  queue
            new_timestamp = time.time()
            if new_timestamp >= old_timestamp + self.RESULT_DRAIN_INTERVAL:
                old_timestamp = new_timestamp
                count_to_remove = ((self.RESULT_DRAIN_MARK // 10) // batch_size)
                if count_to_remove < len(results):
                    if callable(poi_method):
                        map(poi_method, self.quadtrees)
                    while count_to_remove > 0:
                        finished_tile_count += results.popleft().get()
                        self.print_statusline(finished_tile_count,
                            total_tile_count, level)
                        count_to_remove -= 1
            if len(results) > (self.RESULT_DRAIN_MARK // batch_size):
                # Empty the queue before adding any more, so that memory
                # required has an upper bound
                while len(results) > ((self.RESULT_DRAIN_MARK // 20) // batch_size):
                    finished_tile_count += results.popleft().get()
                    self.print_statusline(finished_tile_count,
                        total_tile_count, level)
        # Wait for the rest of the results
        while len(results) > 0:
            finished_tile_count += results.popleft().get()
            self.print_statusline(finished_tile_count, total_tile_count, level)
        if callable(poi_method):
            map(poi_method, self.quadtrees)
        self.print_statusline(finished_tile_count, total_tile_count, level, True)

    def _drain_poi_queue(self, quadtree):
        while True:
            try:
                item = quadtree.poi_queue.get(block=False)
            except Queue.Empty:
                break
            if item[0] == 'newpoi':
                if item[1] not in quadtree.POI:
                    quadtree.POI.append(item[1])
            elif item[0] == 'removePOI':
                quadtree._persistent_data['POI'] = \
                    filter(lambda x: x['chunk'] != item[1],
                        quadtree._persistent_data['POI'])
            elif item[0] == 'rendered':
                self.rendered_tiles.append(item[1])
            
@catch_keyboardinterrupt
def batch_render_world_tiles(batch):
    """
    """
    global CHILD_RENDERNODE
    rendernode = CHILD_RENDERNODE
    count = 0
    for job in batch:
        count += 1
        quadtree = rendernode.quadtrees[job[0]]
        column_start = job[1]
        column_end = job[2]
        row_start = job[3]
        row_end = job[4]
        path = job[5]
        quadtree.render_world_tile(colstart, colend, rowstart, rowend, path)
    return count

@catch_keyboardinterrupt
def batch_render_composed_tiles(batch):
    """
    """
    global CHILD_RENDERNODE
    rendernode = CHILD_RENDERNODE
    count = 0
    for job in batch:
        count += 1
        quadtree = rendernode.quadtrees[job[0]]
        #TODO this should be different
        dest = quadtree.full_tiledir+os.sep+job[1]
        quadtree.render_composed_tile(dest=dest, name=job[2])
    return count
    
class FakeResult(object):
    """
    """
    def __init__(self, res):
        self.res = res

    def get(self):
        return self.res

class FakePool(object):
    """A fake pool used to render things in sync. Implements a subset of
    multiprocessing.Pool
    """
    def apply_async(self, func, args=(), kwargs=None):
        if not kwargs:
            kwargs = {}
        result = func(*args, **kwargs)
        return FakeResult(result)

    def close(self):
        pass

    def join(self):
        pass
    
