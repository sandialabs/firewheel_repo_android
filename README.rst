.. _android_mc_repo:

**********************
firewheel_repo_android
**********************

This repository contains FIREWHEEL model components for Android emulation,
Android-specific VM resources, and Android-oriented test and automation
topologies. Android devices in this repository are launched as native minimega
``android`` VMs and controlled through FIREWHEEL's ADB-based VM Resource
Handler.

It serves as the Android component and reference layer for FIREWHEEL. For
end-to-end workflow tutorials, start with the `FIREWHEEL Android tutorials <https://sandialabs.github.io/firewheel/tutorials/android/index.html>`_.

Installation
============

These model components are intended to be set up through their ``INSTALL``
workflows.

Due to licensing and distribution constraints, some Android SDK, emulator, AVD,
and tool artifacts are reproduced or staged through ``INSTALL`` rather than
being shipped directly in the open-source tree. In normal use, users should run
the relevant ``INSTALL`` workflows instead of manually assembling dependencies.

This includes:

- Android SDK and emulator setup through ``android.base_objects``;
- device-specific assets such as ``android.pixel9a``;
- host-side Maestro installation through ``android.maestro``;
- optional test APK resources used by Android test topologies.

For general background on reproducible resource installation, see the `FIREWHEEL INSTALL tutorial <https://sandialabs.github.io/firewheel/tutorials/install_file.html>`_.

Included Model Components
=========================

This repository currently provides the following primary model components:

- ``android.base_objects``
- ``android.pixel9a``
- ``android.maestro``
- ``android.test_topology``
- ``android.mixed_test_topology``
- ``android.maestro_test_topology``

Adding a New Android Device
===========================

To add support for a new Android device, create a model component similar to
``android.pixel9a`` and provide a corresponding ``INSTALL`` workflow that
stages the device's AVD assets and any required SDK packages.

`Android Studio <https://developer.android.com/studio>`_ can be used to create
or download AVDs. In general, avoid Google Play images when root access is
required for experimentation.

Default ``-read-only`` Behavior
===============================

These Android model components add ``-read-only`` by default through
``android-extra-args`` so that multiple emulators can share the same AVD
definition.

This default supports:

- multiple Android phones using the same AVD;
- larger Android-only topologies;
- mixed Android and Ubuntu topologies.

If ``-read-only`` is disabled while multiple emulators share one AVD, emulator
launch is expected to fail.

Testing and Validation
======================

Use the topology-specific model components as the primary validation entry
points:

- ``android.test_topology`` for Android-only smoke, network, and APK tests;
- ``android.mixed_test_topology`` for Android and Ubuntu mixed-topology validation;
- ``android.maestro_test_topology`` for host-side Maestro automation validation.

Those component docs contain the topology-specific commands, parameters, and
expected behavior.

Troubleshooting
===============

If Android devices fail to launch, inspect the Android emulator log in
FIREWHEEL's ``vm_resource_logs`` directory and verify the runtime ADB details.

Useful commands:

.. code-block:: bash

   minimega -e ".columns name,state,type,android_console_port,android_adb_port,android_serial vm info"

.. code-block:: bash

   adb devices

.. code-block:: bash

   adb -s emulator-5554 shell 'getprop sys.boot_completed; getprop dev.bootcomplete; pm path android'

.. code-block:: bash

   adb -s emulator-5554 shell 'ip addr; ip route; ip rule'

Common issues include missing emulator binaries, launching multiple writable
instances from one shared AVD, missing Python or Bash assumptions in Android VM
resources, split APK installation errors, and lost runtime networking after
reboot.

See Also
========

- `FIREWHEEL Android tutorials <https://sandialabs.github.io/firewheel/tutorials/android/index.html>`_
- `ADB VM Resource Handler documentation <https://sandialabs.github.io/firewheel/system/vm_resource_manager/adb.html>`_
