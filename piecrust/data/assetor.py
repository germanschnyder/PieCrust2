import os
import os.path
import logging
from piecrust.uriutil import multi_replace


logger = logging.getLogger(__name__)


class UnsupportedAssetsError(Exception):
    pass


def build_base_url(app, uri, assets_path):
    base_url_format = app.env.base_asset_url_format
    site_root = app.config.get('site/root')
    rel_path = os.path.relpath(assets_path, app.root_dir).replace('\\', '/')
    pretty = app.config.get('site/pretty_urls')
    if not pretty:
        uri, _ = os.path.splitext(uri)
    uri = uri.lstrip('/')
    base_url = multi_replace(
            base_url_format,
            {
                '%site_root%': site_root,
                '%path%': rel_path,
                '%uri%': uri})
    return base_url.rstrip('/') + '/'


class Assetor(object):
    ASSET_DIR_SUFFIX = '-assets'

    debug_render_doc = """Helps render URLs to files in the current page's
                          asset folder."""
    debug_render = []
    debug_render_dynamic = ['_debugRenderAssetNames']

    def __init__(self, page, uri):
        self._page = page
        self._uri = uri
        self._cache = None

    def __getattr__(self, name):
        try:
            self._cacheAssets()
            return self._cache[name][0]
        except KeyError:
            raise AttributeError()

    def __getitem__(self, key):
        self._cacheAssets()
        return self._cache[key][0]

    def __iter__(self):
        self._cacheAssets()
        return map(lambda i: i[0], self._cache.values())

    def _getAssetPaths(self):
        self._cacheAssets()
        return map(lambda i: i[1], self._cache.values())

    def _debugRenderAssetNames(self):
        self._cacheAssets()
        return list(self._cache.keys())

    def _cacheAssets(self):
        if self._cache is not None:
            return

        self._cache = {}
        name, ext = os.path.splitext(self._page.path)
        assets_dir = name + Assetor.ASSET_DIR_SUFFIX
        if not os.path.isdir(assets_dir):
            return

        base_url = build_base_url(self._page.app, self._uri, assets_dir)
        for fn in os.listdir(assets_dir):
            full_fn = os.path.join(assets_dir, fn)
            if not os.path.isfile(full_fn):
                raise Exception("Skipping: %s" % full_fn)
                continue

            name, ext = os.path.splitext(fn)
            if name in self._cache:
                raise UnsupportedAssetsError(
                        "Multiple asset files are named '%s'." % name)
            self._cache[name] = (base_url + fn, full_fn)

        cpi = self._page.app.env.exec_info_stack.current_page_info
        if cpi is not None:
            cpi.render_ctx.used_assets = self

