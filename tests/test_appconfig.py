import yaml
from piecrust.appconfig import PieCrustConfiguration
from .mockutil import mock_fs, mock_fs_scope


def test_config_default():
    values = {}
    config = PieCrustConfiguration(values=values)
    assert config.get('site/root') == '/'
    assert len(config.get('site/sources')) == 3  # pages, posts, theme_pages


def test_config_default2():
    config = PieCrustConfiguration()
    assert config.get('site/root') == '/'
    assert len(config.get('site/sources')) == 3  # pages, posts, theme_pages


def test_config_site_override_title():
    values = {'site': {'title': "Whatever"}}
    config = PieCrustConfiguration(values=values)
    assert config.get('site/root') == '/'
    assert config.get('site/title') == 'Whatever'


def test_config_override_default_model_settings():
    config = {'site': {
        'default_page_layout': 'foo',
        'default_post_layout': 'bar',
        'posts_per_page': 2}}
    fs = mock_fs().withConfig(config)
    with mock_fs_scope(fs):
        app = fs.getApp()
        assert app.config.get('site/default_page_layout') == 'foo'
        assert app.config.get('site/default_post_layout') == 'bar'
        assert app.config.get('site/sources')['pages']['default_layout'] == 'foo'
        assert app.config.get('site/sources')['pages']['items_per_page'] == 5
        assert app.config.get('site/sources')['theme_pages']['default_layout'] == 'default'
        assert app.config.get('site/sources')['theme_pages']['items_per_page'] == 5
        assert app.config.get('site/sources')['posts']['default_layout'] == 'bar'
        assert app.config.get('site/sources')['posts']['items_per_page'] == 2

def test_config_site_add_source():
    config = {'site': {
        'sources': {'notes': {}},
        'routes': [{'url': '/notes/%path:slug%', 'source': 'notes'}]
        }}
    fs = mock_fs().withConfig(config)
    with mock_fs_scope(fs):
        app = fs.getApp()
        # The order of routes is important. Sources, not so much.
        assert (list(
            map(
                lambda v: v.get('generator') or v['source'],
                app.config.get('site/routes'))) ==
            ['notes', 'posts', 'posts_archives', 'posts_tags', 'posts_categories', 'pages', 'theme_pages'])
        assert list(app.config.get('site/sources').keys()) == [
            'theme_pages', 'pages', 'posts', 'notes']


def test_config_site_add_source_in_both_site_and_theme():
    theme_config = {'site': {
        'sources': {'theme_notes': {}},
        'routes': [{'url': '/theme_notes/%path:slug%', 'source': 'theme_notes'}]
        }}
    config = {'site': {
        'sources': {'notes': {}},
        'routes': [{'url': '/notes/%path:slug%', 'source': 'notes'}]
        }}
    fs = (mock_fs()
            .withConfig(config)
            .withFile('kitchen/theme/theme_config.yml', yaml.dump(theme_config)))
    with mock_fs_scope(fs):
        app = fs.getApp()
        # The order of routes is important. Sources, not so much.
        # `posts` shows up 3 times in routes (posts, tags, categories)
        assert (list(
            map(
                lambda v: v.get('generator') or v['source'],
                app.config.get('site/routes'))) ==
            ['notes', 'posts', 'posts_archives', 'posts_tags', 'posts_categories', 'pages', 'theme_notes', 'theme_pages'])
        assert list(app.config.get('site/sources').keys()) == [
            'theme_pages', 'theme_notes', 'pages', 'posts', 'notes']

