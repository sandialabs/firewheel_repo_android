.. _android.maestro_test_topology_mc:

#############################
android.maestro_test_topology
#############################

The ``android.maestro_test_topology`` model component provides a small test
topology for validating the :ref:`android.maestro_mc` model component.

For a tutorial-driven workflow example, see the published `Android automation
tutorial <https://sandialabs.github.io/firewheel/tutorials/android/android_app_automation.html>`_.

It launches a single Android Pixel 9a emulator and schedules one or more
host-side Maestro flows against it.

This topology is primarily intended for testing and debugging the interaction
between :ref:`android.maestro_mc` and :ref:`android.pixel9a_mc`. It can also
serve as a compact example of how to use Maestro in a FIREWHEEL experiment.

**Model Component Dependencies:**
    * :ref:`android.maestro_mc`
    * :ref:`android.pixel9a_mc`


Overview
========

The topology creates one Android phone and, depending on the selected
``test_case``, schedules one or more Maestro flows from the
``android.maestro`` example flow resources.

The details of host-side execution, ADB serial resolution, and artifact layout
are documented in :ref:`android.maestro_mc`. This page focuses on the topology's
parameters and test cases.


Usage
=====

Basic command:

.. code-block:: bash

   firewheel experiment android.maestro_test_topology:test_case=settings_check minimega.launch -r

Run all normal passing Maestro example flows:

.. code-block:: bash

   firewheel experiment android.maestro_test_topology:test_case=all minimega.launch -r

Run the expected failure flow:

.. code-block:: bash

   firewheel experiment android.maestro_test_topology:test_case=expected_failure minimega.launch -r


Parameters
==========

``test_case``
    Which Maestro test case to run.

    Supported values:

    ``settings_check``
        Launches Android Settings and asserts that a known top-level Settings
        item is visible.

    ``settings_network``
        Launches Android Settings, taps ``Network & internet``, and asserts that
        the network settings page is visible.

    ``settings_search``
        Launches Android Settings and exercises Settings search/text input.

    ``expected_failure``
        Runs a Maestro flow that is expected to fail. This is useful for testing
        failure artifacts and result handling.

    ``all``
        Runs the normal passing example flows. This includes:

        * ``settings_check``
        * ``settings_network``
        * ``settings_search``

        It does not include ``expected_failure``.

``start_time``
    Schedule time for the first Maestro flow. Defaults to ``10``.

``timeout``
    Timeout, in seconds, for each Maestro flow. Defaults to ``120``.

``fail_experiment_on_failure``
    If set to ``true``, a Maestro failure causes the host-side runner to exit
    nonzero.

    Defaults to ``false``.


Examples
========

Settings Check
--------------

Run the basic Settings check:

.. code-block:: bash

   firewheel experiment android.maestro_test_topology:test_case=settings_check minimega.launch -r

Network Settings
----------------

Run the network settings flow:

.. code-block:: bash

   firewheel experiment android.maestro_test_topology:test_case=settings_network minimega.launch -r

Settings Search
---------------

Run the Settings search flow:

.. code-block:: bash

   firewheel experiment android.maestro_test_topology:test_case=settings_search minimega.launch -r

All Passing Flows
-----------------

Run all normal passing example flows:

.. code-block:: bash

   firewheel experiment android.maestro_test_topology:test_case=all minimega.launch -r

The flows are staggered in time to avoid concurrent control of the same emulator.


Expected Failure
----------------

Run the deliberately failing flow:

.. code-block:: bash

   firewheel experiment android.maestro_test_topology:test_case=expected_failure minimega.launch -r

By default, this should produce a Maestro failure in ``result.json`` but should
not fail the overall Maestro process.

To make this failure propagate as a nonzero host-resource exit:

.. code-block:: bash

   firewheel experiment android.maestro_test_topology:test_case=expected_failure:fail_experiment_on_failure=true minimega.launch -r


Artifacts
=========

Maestro runner artifacts are written under FIREWHEEL's logging root. For the
artifact directory layout, captured files, and result semantics, see
:ref:`android.maestro_mc`.

In this topology, the VM name is usually ``android-0`` and the most important
artifact is typically ``result.json``.

Available Plugin
================

.. autoclass:: android.maestro_test_topology.AndroidMaestroTestTopology
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :show-inheritance:
    :exclude-members: __dict__,__weakref__,__module__
