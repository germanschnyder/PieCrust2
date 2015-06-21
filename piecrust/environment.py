import time
import logging
import contextlib
from piecrust.cache import MemCache


logger = logging.getLogger(__name__)


class ExecutionInfo(object):
    def __init__(self, page, render_ctx):
        self.page = page
        self.render_ctx = render_ctx
        self.was_cache_valid = False
        self.start_time = time.perf_counter()


class ExecutionInfoStack(object):
    def __init__(self):
        self._page_stack = []

    @property
    def current_page_info(self):
        if len(self._page_stack) == 0:
            return None
        return self._page_stack[-1]

    @property
    def is_main_page(self):
        return len(self._page_stack) == 1

    def hasPage(self, page):
        for ei in self._page_stack:
            if ei.page == page:
                return True
        return False

    def pushPage(self, page, render_ctx):
        if len(self._page_stack) > 0:
            top = self._page_stack[-1]
            assert top.page is not page
        self._page_stack.append(ExecutionInfo(page, render_ctx))

    def popPage(self):
        del self._page_stack[-1]

    def clear(self):
        self._page_stack = []


class Environment(object):
    def __init__(self):
        self.start_time = None
        self.exec_info_stack = ExecutionInfoStack()
        self.was_cache_cleaned = False
        self.base_asset_url_format = '%uri%'
        self.page_repository = MemCache()
        self.rendered_segments_repository = MemCache()
        self.fs_caches = {
                'renders': self.rendered_segments_repository}
        self.fs_cache_only_for_main_page = False
        self._timers = {}

    def initialize(self, app):
        self.start_time = time.perf_counter()
        self.exec_info_stack.clear()
        self.was_cache_cleaned = False
        self.base_asset_url_format = '%uri%'
        self._onSubCacheDirChanged(app)

    def registerTimer(self, category, *, raise_if_registered=True):
        if raise_if_registered and category in self._timers:
            raise Exception("Timer '%s' has already been registered." %
                            category)
        self._timers[category] = 0

    @contextlib.contextmanager
    def timerScope(self, category):
        start = time.perf_counter()
        yield
        self._timers[category] += time.perf_counter() - start

    def stepTimer(self, category, value):
        self._timers[category] += value

    def _onSubCacheDirChanged(self, app):
        for name, repo in self.fs_caches.items():
            cache = app.cache.getCache(name)
            repo.fs_cache = cache


class StandardEnvironment(Environment):
    def __init__(self):
        super(StandardEnvironment, self).__init__()

