import sys
import json
import codecs
import datetime
import collections


def pickle(obj):
    data = _pickle_object(obj)
    data = json.dumps(data, indent=None, separators=(',', ':'))
    return data.encode('utf8')


def pickle_obj(obj):
    if obj is not None:
        return _pickle_object(obj)
    return None


def pickle_intob(obj, buf):
    data = _pickle_object(obj)
    buf = _WriteWrapper(buf)
    json.dump(data, buf, indent=None, separators=(',', ':'))


def unpickle(data):
    data = json.loads(data.decode('utf8'))
    return _unpickle_object(data)


def unpickle_obj(data):
    if data is not None:
        return _unpickle_object(data)
    return None


def unpickle_fromb(buf, bufsize):
    with buf.getbuffer() as innerbuf:
        data = codecs.decode(innerbuf[:bufsize], 'utf8')
    data = json.loads(data)
    return _unpickle_object(data)


class _WriteWrapper(object):
    def __init__(self, buf):
        self._buf = buf

    def write(self, data):
        self._buf.write(data.encode('utf8'))


_PICKLING = 0
_UNPICKLING = 1

_identity_dispatch = object()


def _tuple_convert(obj, func, op):
    if op == _PICKLING:
        return ['__type__:tuple'] + [func(c) for c in obj]
    elif op == _UNPICKLING:
        return tuple([func(c) for c in obj[1:]])


def _list_convert(obj, func, op):
    return [func(c) for c in obj]


def _dict_convert(obj, func, op):
    res = {}
    for k, v in obj.items():
        res[k] = func(v)
    return res


def _ordered_dict_convert(obj, func, op):
    if op == _PICKLING:
        res = {'__type__': 'OrderedDict'}
        for k, v in obj.items():
            res[k] = func(v)
        return res
    elif op == _UNPICKLING:
        res = collections.OrderedDict()
        for k, v in obj.items():
            if k != '__type__':
                res[k] = func(v)
        return res


def _set_convert(obj, func, op):
    if op == _PICKLING:
        return ['__type__:set'] + [func(c) for c in obj]
    elif op == _UNPICKLING:
        return set([func(c) for c in obj[1:]])


def _date_convert(obj, func, op):
    if op == _PICKLING:
        return {'__class__': 'date',
                'year': obj.year,
                'month': obj.month,
                'day': obj.day}
    elif op == _UNPICKLING:
        return datetime.date(
                obj['year'], obj['month'], obj['day'])


def _datetime_convert(obj, func, op):
    if op == _PICKLING:
        return {'__class__': 'datetime',
                'year': obj.year,
                'month': obj.month,
                'day': obj.day,
                'hour': obj.hour,
                'minute': obj.minute,
                'second': obj.second,
                'microsecond': obj.microsecond}
    elif op == _UNPICKLING:
        return datetime.datetime(
                obj['year'], obj['month'], obj['day'],
                obj['hour'], obj['minute'], obj['second'], obj['microsecond'])


def _time_convert(obj, func, op):
    if op == _PICKLING:
        return {'__class__': 'time',
                'hour': obj.hour,
                'minute': obj.minute,
                'second': obj.second,
                'microsecond': obj.microsecond}
    elif op == _UNPICKLING:
        return datetime.time(
                obj['hour'], obj['minute'], obj['second'], obj['microsecond'])


_type_convert = {
        type(None): _identity_dispatch,
        bool: _identity_dispatch,
        int: _identity_dispatch,
        float: _identity_dispatch,
        str: _identity_dispatch,
        datetime.date: _date_convert,
        datetime.datetime: _datetime_convert,
        datetime.time: _time_convert,
        tuple: _tuple_convert,
        list: _list_convert,
        dict: _dict_convert,
        set: _set_convert,
        collections.OrderedDict: _ordered_dict_convert,
        }


_type_unconvert = {
        type(None): _identity_dispatch,
        bool: _identity_dispatch,
        int: _identity_dispatch,
        float: _identity_dispatch,
        str: _identity_dispatch,
        'date': _date_convert,
        'datetime': _datetime_convert,
        'time': _time_convert,
        }


_collection_unconvert = {
        '__type__:tuple': _tuple_convert,
        '__type__:set': _set_convert,
        }


_mapping_unconvert = {
        'OrderedDict': _ordered_dict_convert
        }


def _pickle_object(obj):
    t = type(obj)
    conv = _type_convert.get(t)

    # Object doesn't need conversion?
    if conv is _identity_dispatch:
        return obj

    # Object has special conversion?
    if conv is not None:
        return conv(obj, _pickle_object, _PICKLING)

    # Use instance dictionary, or a custom state.
    getter = getattr(obj, '__getstate__', None)
    if getter is not None:
        state = getter()
    else:
        state = obj.__dict__

    state = _dict_convert(state, _pickle_object, _PICKLING)
    state['__class__'] = obj.__class__.__name__
    state['__module__'] = obj.__class__.__module__

    return state


def _unpickle_object(state):
    t = type(state)
    conv = _type_unconvert.get(t)

    # Object doesn't need conversion?
    if conv is _identity_dispatch:
        return state

    # Try collection or mapping conversion.
    if t is list:
        try:
            col_type = state[0]
            if not isinstance(col_type, str):
                col_type = None
        except IndexError:
            col_type = None
        if col_type is not None:
            conv = _collection_unconvert.get(col_type)
            if conv is not None:
                return conv(state, _unpickle_object, _UNPICKLING)
        return _list_convert(state, _unpickle_object, _UNPICKLING)

    assert t is dict

    # Custom mapping type?
    map_type = state.get('__type__')
    if map_type:
        conv = _mapping_unconvert.get(map_type)
        return conv(state, _unpickle_object, _UNPICKLING)

    # Class instance or other custom type.
    class_name = state.get('__class__')
    if class_name is None:
        return _dict_convert(state, _unpickle_object, _UNPICKLING)

    conv = _type_unconvert.get(class_name)
    if conv is not None:
        return conv(state, _unpickle_object, _UNPICKLING)

    mod_name = state['__module__']
    mod = sys.modules[mod_name]
    class_def = getattr(mod, class_name)
    obj = class_def.__new__(class_def)

    attr_names = list(state.keys())
    for name in attr_names:
        if name == '__class__' or name == '__module__':
            continue
        obj.__dict__[name] = _unpickle_object(state[name])

    return obj

