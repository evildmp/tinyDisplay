..  _how-to:

How-to guides
==============

How to install tinyDisplay
--------------------------

tinyDisplay uses `Poetry <https://python-poetry.org/docs/>`_ to manage installation and dependencies.

Clone the tinyDisplay repository, and in the repository directory run:

..  code-block:: bash

    poetry install


How to run tests
----------------

tinyDisplay's test suite can be found in ``tests``. The test suite requires Pytest, which is installed by default.

Execute ``pytest`` to run all tests.


How to build the documentation
------------------------------------

The documentation is all in the project's ``docs`` directory. The ``Makefile`` includes a number of useful commands
that can be run in that directory.

Install documentation components locally in a virtualenv:

..  code-block:: bash

    cd docs
    make install

Build HTML:

..  code-block:: bash

    make html
    open _build/html/index.html

Or, run a documentation server:

..  code-block:: bash

    make run

\ - the documentation will be served at http://localhost:8901

See also :ref:`documentation-standards`.
