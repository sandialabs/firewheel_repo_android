.. _android.test_topology_mc:

#####################
android.test_topology
#####################

This model component provides a parameterized test topology for Android devices.
It can launch one or more Google Pixel 9a phones, optionally connect them to a switch,
run Android-native ping tests, and install APKs.

The topology is intended to validate the behavior provided by
:ref:`android.base_objects_mc` and :ref:`android.pixel9a_mc`, including:

* Android emulator launch through minimega's native ``android`` VM type;
* ADB-based VM Resource Handler connectivity;
* multiple Android phones sharing one AVD with default ``-read-only`` behavior;
* Android runtime IP configuration;
* Android-to-Android network connectivity;
* APK installation while the AVD is in read-only mode.

**Model Component Dependencies:**
    * :ref:`android.pixel9a_mc`


INSTALL
=======

This model component includes an ``INSTALL`` directory that downloads generic
APK files used by the APK installation tests. The APKs are placed in
``vm_resources/`` and are treated as normal FIREWHEEL VM resources.
The APK URLs are version-pinned and checksums are verified during installation.

The downloaded APKs are intended only to validate Android package installation
behavior. They are not required for ``smoke`` or ``network`` test cases.

For offline use, provide the APKs through the FIREWHEEL cache using the
``required_files`` entries in ``INSTALL/vars.yml``.


Example Usage
=============

For a tutorial-style introduction to Android experiments before using this test
component, see the published `Android experiment tutorial <https://sandialabs.github.io/firewheel/tutorials/android/android_app_setup.html>`_.

All examples below use ``-r`` so FIREWHEEL restarts the experiment state as needed:

.. code-block:: bash

   firewheel experiment android.test_topology:size=1:test_case=smoke minimega.launch -r

Parameters
==========

``size``
    Number of Android phones to launch.

    Defaults to ``1``.

``test_case``
    Which Android test case to run.

    Supported values:

    ``smoke``
        Launch one or more Android phones without extra test resources.

    ``same_avd``
        Launch multiple Android phones from the same AVD using the default
        shared-AVD ``-read-only`` behavior.

    ``network``
        Launch multiple Android phones connected to a FIREWHEEL switch and run
        Android-native ping tests.

    ``apk``
        Install one or more APKs on each Android phone.

    ``network_apk``
        Run both the network and APK installation tests.

    ``all``
        Alias for the combined network and APK test.

    ``no_read_only_negative``
        Disable the default ``-read-only`` behavior as a negative test for
        shared-AVD launches.

    Defaults to ``smoke``.

``apk``
    APK filename, or comma-separated APK filenames, for APK-oriented test cases.

    Defaults to ``wikipedia.apk``.

``start_apk``
    Schedule time for APK installation.

    Defaults to ``-50``.

``start_ping``
    Schedule time for the ping test.

    Defaults to ``1``.


Supported Test Cases
====================

``smoke``
---------

Launch one or more Android phones without extra test resources. This is the
minimal launch test and verifies that the Android VM can start successfully.

.. code-block:: bash

   firewheel experiment android.test_topology:size=1:test_case=smoke minimega.launch -r

``same_avd``
------------

Launch multiple Android phones from the same AVD using the default
``-read-only`` behavior.

.. code-block:: bash

   firewheel experiment android.test_topology:size=2:test_case=same_avd minimega.launch -r

This validates that multiple phones can share the same AVD definition.

``network``
-----------

Launch multiple Android phones connected to a FIREWHEEL switch and run an
Android-native ping test.

.. code-block:: bash

   firewheel experiment android.test_topology:size=2:test_case=network minimega.launch -r

The phones are assigned addresses in the ``1.0.0.0/8`` network. For example,
with ``size=2``:

* ``android-0`` receives ``1.0.0.1/8``;
* ``android-1`` receives ``1.0.0.2/8``.

``apk``
-------

Install one or more APKs on each Android phone.

The INSTALL step provides two generic test APKs in ``vm_resources/``:

* ``wikipedia.apk`` -- Wikipedia Android app.
* ``vlc.apk`` -- VLC for Android x86_64 APK.

APK test cases default to ``wikipedia.apk``.

.. code-block:: bash

   firewheel experiment android.test_topology:size=1:test_case=apk:apk=wikipedia.apk minimega.launch -r

To test VLC installation instead:

.. code-block:: bash

   firewheel experiment android.test_topology:size=1:test_case=apk:apk=vlc.apk minimega.launch -r

Multiple independent APKs may be passed as a comma-separated list:

.. code-block:: bash

   firewheel experiment android.test_topology:size=1:test_case=apk:apk=wikipedia.apk,vlc.apk minimega.launch -r

These are treated as independent APK installs, not as one split APK package.

``network_apk``
---------------

Run both the network and APK installation tests.

.. code-block:: bash

   firewheel experiment android.test_topology:size=2:test_case=network_apk:apk=wikipedia.apk minimega.launch -r

``all``
-------

Alias for the combined network and APK test.

.. code-block:: bash

   firewheel experiment android.test_topology:size=2:test_case=all:apk=wikipedia.apk minimega.launch -r

``no_read_only_negative``
-------------------------

Disable the default ``-read-only`` flag. This is a negative test when launching
more than one phone using the same AVD.

.. code-block:: bash

   firewheel experiment android.test_topology:size=2:test_case=no_read_only_negative minimega.launch -r

This is expected to fail for shared AVDs and is useful for verifying that
``-read-only`` is required for multi-phone shared-AVD experiments.

This negative test requires ``size >= 2`` because it is specifically validating
multiple Android phones attempting to share one writable AVD.

APK Notes
=========

To use a custom APK, ensure it is available as a VM resource and pass its
basename with ``apk=<filename>.apk``.

For the underlying Android APK installation behavior, readiness checks, and
split-package semantics, see :ref:`android.base_objects_mc`.

Complete APKs can be installed directly. Split APKs require all required split
files and must be installed as a split package. A missing split typically
produces an error like:

.. code-block:: text

   INSTALL_FAILED_MISSING_SPLIT

The test topology's comma-separated APK list is intended for multiple
independent APKs unless explicitly documented otherwise.

Android Runtime Notes
=====================

See :ref:`firewheel_repo_android <android_mc_repo>` and
:ref:`android.base_objects_mc` for general Android runtime behavior,
installation expectations, and troubleshooting.

Plugin
======

.. automodule:: android.test_topology_plugin
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :show-inheritance:
    :exclude-members: __dict__,__weakref__,__module__
