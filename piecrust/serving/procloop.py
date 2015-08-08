import os
import os.path
import time
import json
import queue
import logging
import itertools
import threading


logger = logging.getLogger(__name__)

# This flag is for cancelling all long running requests like SSEs.
server_shutdown = False


class PipelineStatusServerSentEventProducer(object):
    """ The producer for Server-Sent Events (SSE) notifying the front-end
        about useful things like assets having been re-processed in the
        background.
        Each has its own queue because the user could have multiple pages
        open, each having to display notifications coming from the server.
    """
    def __init__(self, proc_loop):
        self._proc_loop = proc_loop
        self._queue = queue.Queue()
        self._start_time = 0
        self._poll_interval = 0.5
        self._ping_interval = 30
        self._time_between_pings = 0
        self._running = 0

    def addBuildEvent(self, item):
        self._queue.put_nowait(item)

    def run(self):
        logger.debug("Starting pipeline status SSE.")
        self._proc_loop.addObserver(self)
        self._start_time = time.time()
        self._running = 1

        outstr = 'event: ping\ndata: started\n\n'
        yield bytes(outstr, 'utf8')

        while self._running == 1 and not server_shutdown:
            try:
                # We use a short poll interval (less than a second) because
                # we need to catch `server_shutdown` going `True` as soon as
                # possible to exit this thread when the user hits `CTRL+C`.
                data = self._queue.get(True, self._poll_interval)
            except queue.Empty:
                # Not exact timing but close enough.
                self._time_between_pings += self._poll_interval
                if self._time_between_pings >= self._ping_interval:
                    self._time_between_pings = 0
                    logger.debug("Sending ping/heartbeat event.")
                    outstr = 'event: ping\ndata: 1\n\n'
                    yield bytes(outstr, 'utf8')
                continue

            logger.debug("Sending pipeline status SSE.")
            outstr = (('event: %s\n' % data['type']) +
                      ('id: %s\n' % data['id']) +
                      ('data: %s\n\n' % json.dumps(data)))
            self._queue.task_done()
            yield bytes(outstr, 'utf8')

    def close(self):
        logger.debug("Closing pipeline status SSE.")
        self._proc_loop.removeObserver(self)
        self._running = 2


class ProcessingLoop(threading.Thread):
    def __init__(self, pipeline):
        super(ProcessingLoop, self).__init__(
                name='pipeline-reloader', daemon=True)
        self.pipeline = pipeline
        self.last_status_id = 0
        self.interval = 1
        self._paths = set()
        self._record = None
        self._last_bake = 0
        self._obs = []
        self._obs_lock = threading.Lock()

    def addObserver(self, obs):
        with self._obs_lock:
            self._obs.append(obs)

    def removeObserver(self, obs):
        with self._obs_lock:
            self._obs.remove(obs)

    def run(self):
        # Build the first list of known files and run the pipeline once.
        app = self.pipeline.app
        roots = [os.path.join(app.root_dir, r)
                 for r in self.pipeline.mounts.keys()]
        for root in roots:
            for dirpath, dirnames, filenames in os.walk(root):
                self._paths |= set([os.path.join(dirpath, f)
                                    for f in filenames])
        self._last_bake = time.time()
        self._record = self.pipeline.run()

        while True:
            for root in roots:
                # For each mount root we try to find the first new or
                # modified file. If any, we just run the pipeline on
                # that mount.
                found_new_or_modified = False
                for dirpath, dirnames, filenames in os.walk(root):
                    for filename in filenames:
                        path = os.path.join(dirpath, filename)
                        if path not in self._paths:
                            logger.debug("Found new asset: %s" % path)
                            self._paths.add(path)
                            found_new_or_modified = True
                            break
                        if os.path.getmtime(path) > self._last_bake:
                            logger.debug("Found modified asset: %s" % path)
                            found_new_or_modified = True
                            break

                    if found_new_or_modified:
                        break

                if found_new_or_modified:
                    self._runPipeline(root)

            time.sleep(self.interval)

    def _runPipeline(self, root):
        self._last_bake = time.time()
        try:
            self._record = self.pipeline.run(
                    root,
                    previous_record=self._record,
                    save_record=False)

            status_id = self.last_status_id + 1
            self.last_status_id += 1

            if self._record.success:
                changed = filter(
                        lambda i: not i.was_collapsed_from_last_run,
                        self._record.entries)
                changed = itertools.chain.from_iterable(
                        map(lambda i: i.rel_outputs, changed))
                changed = list(changed)
                item = {
                        'id': status_id,
                        'type': 'pipeline_success',
                        'assets': changed}

                self._notifyObservers(item)
            else:
                item = {
                        'id': status_id,
                        'type': 'pipeline_error',
                        'assets': []}
                for entry in self._record.entries:
                    if entry.errors:
                        asset_item = {
                                'path': entry.rel_input,
                                'errors': list(entry.errors)}
                        item['assets'].append(asset_item)

                self._notifyObservers(item)
        except Exception as ex:
            logger.exception(ex)

    def _notifyObservers(self, item):
        with self._obs_lock:
            observers = list(self._obs)
        for obs in observers:
            obs.addBuildEvent(item)

