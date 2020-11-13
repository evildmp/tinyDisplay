..  _background:

Background
==========

tinyDisplay has evolved from functionality in `pydPiper <https://github.com/dhrone/pydPiper>`_, an application to
display metadata from music players such as Volumio, MoodeAudio, and Max2Play on small screens.

tinyDisplay uses the `luma.core <https://luma-core.readthedocs.io>`_ library as a display driver - any
display supported by luma will work with tinyDisplay.


Related projects in progress
--------------------------------

pyAttention: data services to listen for music metadata (Volumio, MPD, LMS, etc). Will also support other interfaces
including REST and RSS.

pydPiper: a wholly new version of pydPiper will make use of the functionality of tinyDisplay, luma and pyAttention in
a single project.
