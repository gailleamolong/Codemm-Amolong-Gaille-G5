from django.core.cache import cache


def hits(key):
    return cache.get(key, 0)


def record(key, window_seconds):
    if cache.add(key, 1, window_seconds):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        cache.add(key, 1, window_seconds)
        return 1


def clear(key):
    cache.delete(key)
