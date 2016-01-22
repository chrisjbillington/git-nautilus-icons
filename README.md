# git-nautilus-icons

Use git? Use Nautilus? Why not have nautilus give you info about your repos
with overlaid icons?

git-na
`inotify_init()` is wrapped as a class that does little more than hold the
resulting inotify file descriptor. A `read()` method is provided which reads
available data from the file descriptor and returns events as `namedtuple`
objects after unpacking them with the `struct` module. `inotify_add_watch()`
and `inotify_rm_watch()` are wrapped with no changes at all, taking and
returning watch descriptor integers that calling code is expected to keep
track of itself, just as one would use inotify from C. Works with Python 2 or
3.

[View on PyPI](http://pypi.python.org/pypi/inotify_simple) |
[Fork me on github](https://github.com/chrisjbillington/inotify_simple) |
[Read the docs](http://inotify_simple.readthedocs.org)


## Installation

to install `inotify_simple`, run:

```
$ pip install inotify_simple
```

or to install from source:

```
$ python setup.py install
```

Note:  If on Python < 3.4, you'll need the backported [enum34
module](https://pypi.python.org/pypi/enum34).

