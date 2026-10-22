.. _android.pixel9a_mc:

###############
android.pixel9a
###############

This model component provides objects to create a Pixel9a Android device.
It heavily relies on functionality from :ref:`android.base_objects <android.base_objects_mc>`.

The Pixel9a component provides a concrete Android device/AVD configuration. It
copies the Pixel 9a AVD files into the Android base component's ``.android/avd``
directory and configures the Android phone to launch the ``Pixel_9a`` AVD.

Prerequisites
=============

Before using this model component, run the relevant ``INSTALL`` workflows for
:ref:`android.base_objects_mc` and ``android.pixel9a``.

The Pixel 9a ``INSTALL`` workflow is the normal way to prepare this component.
It can use the optional offline/cache archive ``Pixel_9a.avd.tgz`` when
provided, or create the Pixel 9a AVD locally when the archive is absent.

After INSTALL, this component expects the following paths to exist inside the
model component directory:

* ``Pixel_9a.avd``
* ``Pixel_9a.ini``

``Pixel_9a.ini`` is written and managed by the Pixel 9a ``INSTALL`` workflow as
part of the relocatable runtime AVD layout. It is not intended to be a static
user-supplied file.

AVD Installation Behavior
=========================

The Pixel 9a ``INSTALL`` workflow can stage the Pixel 9a AVD content or create
it locally, and ensures that the required SDK packages for this device are
present. At runtime, the Pixel 9a AVD is copied into the Android base
component's AVD directory:

.. code-block:: text

   android_base/.android/avd/

The AVD is installed once per experiment graph-processing run. Additional Pixel
9a phones in the same topology reuse the already-installed AVD definition.

This component sets the Android Virtual Device name to:

.. code-block:: text

   Pixel_9a

The AVD name is also used as the Android VM's image-like identifier for FIREWHEEL
metadata and output where applicable.

Read-only AVD Behavior
======================

The Android base component defaults to launching Android emulators with
``-read-only``. This is important for Pixel9a topologies that launch more than
one phone from the same AVD.

Removing ``-read-only`` while launching multiple Pixel9a phones from the shared
AVD is expected to fail because the Android emulator does not normally allow
multiple writable emulator instances using the same AVD directory.

See :ref:`android.base_objects_mc` and
:ref:`firewheel_repo_android <android_mc_repo>` for broader Android runtime
behavior and limitations.

**Model Component Dependencies:**
    * :ref:`android.base_objects_mc`

*****************
Available Objects
*****************

.. automodule:: android.pixel9a
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :show-inheritance:
    :exclude-members: __dict__,__weakref__,__module__
