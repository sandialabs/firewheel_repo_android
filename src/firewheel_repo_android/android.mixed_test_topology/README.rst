.. _android.mixed_test_topology_mc:

###########################
android.mixed_test_topology
###########################

This model component provides a mixed Android and Ubuntu topology for validating
that Android/ADB VM Resource Handler support works alongside conventional
Linux/QEMU Guest Agent VMs in the same FIREWHEEL experiment.

The topology creates one or more Android Pixel 9a phones and one or more
Ubuntu 22.04 servers connected to a shared switch.

This test is useful for validating the interaction between
:ref:`android.pixel9a_mc` and :ref:`linux.ubuntu2204_mc`, including:

* Android VMs launched through minimega's native ``android`` VM type;
* Android VM Resource Handler communication through the ``ADB`` driver;
* Ubuntu VM Resource Handler communication through the QEMU Guest Agent driver;
* mixed Android/Linux experiment readiness;
* Android-to-Ubuntu network connectivity;
* Ubuntu-to-Android network connectivity;

**Model Component Dependencies:**
    * :ref:`android.pixel9a_mc`
    * :ref:`linux.ubuntu2204_mc`

Example Usage
=============

For a tutorial-style introduction to Android experiments before moving on to
mixed topologies, see the published `Android experiment tutorial <https://sandialabs.github.io/firewheel/tutorials/android/android_app_setup.html>`_.


All examples below use ``-r`` so FIREWHEEL restarts the experiment state as needed:

Single Android and Single Ubuntu
--------------------------------

.. code-block:: bash

   firewheel experiment android.mixed_test_topology:android_count=1:ubuntu_count=1 minimega.launch -r

Larger Mixed Topology
---------------------

.. code-block:: bash

   firewheel experiment android.mixed_test_topology:android_count=2:ubuntu_count=2 minimega.launch -r

Topology Layout
===============

The topology creates a single switch and connects all Android and Ubuntu VMs to
that switch.

Addresses are allocated with ``netaddr`` from separate pools for readability,
while all VM interfaces use a broad ``10.0.0.0/8`` netmask so the VMs are
directly reachable on the shared switch without a router.

Android phones are allocated from:

.. code-block:: text

   10.0.0.0/24

Ubuntu servers are allocated from:

.. code-block:: text

   10.0.1.0/24

All VM interfaces use netmask:

.. code-block:: text

   255.0.0.0

For example, with ``android_count=2`` and ``ubuntu_count=2``:

.. list-table::
   :header-rows: 1

   * - VM
     - Address
   * - ``android-0``
     - ``10.0.0.1/8``
   * - ``android-1``
     - ``10.0.0.2/8``
   * - ``server-0``
     - ``10.0.1.1/8``
   * - ``server-1``
     - ``10.0.1.2/8``

If more VMs are requested than the allocation pools can support, the plugin
raises an error before launching the experiment.

Parameters
==========

``android_count``
    Number of Android Pixel 9a phones to create.

    Defaults to ``1``.

``ubuntu_count``
    Number of Ubuntu 22.04 server VMs to create.

    Defaults to ``1``.

``start_ping``
    Schedule time for ping tests.

    Defaults to ``1``.

Expected Behavior
=================

A successful mixed-topology run should show:

* Android VMs in minimega with type ``android``;
* Ubuntu VMs in minimega as conventional QEMU/KVM VMs;
* Android VMs with populated ``android_serial``, ``android_console_port``, and
  ``android_adb_port`` fields;
* Android VM Resource Handlers using the ``ADB`` communication driver;
* Ubuntu VM Resource Handlers using the QEMU Guest Agent communication driver;
* all VMs reaching the configured state;
* the experiment start time being set after both Android and Ubuntu VMs are
  ready.

Useful validation commands:

.. code-block:: bash

   minimega -e ".columns name,type,state,android_console_port,android_adb_port,android_serial vm info"

.. code-block:: bash

   adb devices

.. code-block:: bash

   adb -s emulator-5554 shell 'ip addr; ip route; ip rule'

Android-to-Ubuntu Connectivity
==============================

Android phones use Android's native ``/system/bin/ping`` command to ping the
Ubuntu servers. This avoids relying on Python, Bash, or Linux distribution
helper scripts inside Android. For the broader Android runtime assumptions
behind this behavior, see :ref:`android.base_objects_mc`.

Ubuntu-to-Android Connectivity
==============================

Ubuntu servers run normal Linux ping commands to ping the Android phones.

If Android-to-Ubuntu ping succeeds but Ubuntu-to-Android ping fails, inspect:

* Android IP configuration;
* Android routes and policy rules;
* Ubuntu IP configuration;
* minimega bridge/tap connectivity;
* firewall rules on either side.

Android Runtime Notes
=====================

See :ref:`firewheel_repo_android <android_mc_repo>`,
:ref:`android.base_objects_mc`, and :ref:`linux.ubuntu2204_mc` for the
component-level runtime assumptions behind this mixed topology.

Plugin
======

.. automodule:: android.mixed_test_topology_plugin
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :show-inheritance:
    :exclude-members: __dict__,__weakref__,__module__
