.. _android.base_objects_mc:

####################
android.base_objects
####################

This model component provides the ``AndroidPhone`` object and Android-specific
functionality shared by Android FIREWHEEL model components.

It provides:

* native minimega ``android`` VM launch configuration;
* ADB-based VM Resource Handler configuration;
* model-component-local Android SDK, emulator, and VM resource installation via
  ``INSTALL``;
* Android runtime network configuration helpers;
* Android-safe hostname setup;
* optional APK installation helpers;
* default support for launching multiple emulators from the same AVD using
  ``-read-only``.

Android VMs are launched through minimega's native ``android`` VM type.

Installation and Provisioning
=============================

This model component includes an ``INSTALL`` workflow that provisions the
Android host-side environment required by FIREWHEEL.

The ``INSTALL`` tasks can:

* install supported host OS packages for Debian/Ubuntu and RHEL-family hosts;
* stage or extract a model-component-local Android SDK;
* install Android SDK packages such as ``platform-tools``, ``emulator``,
  platforms, build-tools, and system images;
* create a model-component-local ``.android`` directory and ``repositories.cfg``;
* generate a local ADB key when configured;
* stage Android VM resources used by this repository, including Termux/Bash
  support artifacts that enable optional Android-side Bash workflows.

Offline/cache archives of ``INSTALL`` files (e.g., ``Android.tgz``) are
supported in the ``INSTALL`` workflow.

Configuration Layers
====================

The Android base component configures two distinct layers.

minimega Android Launch Configuration
-------------------------------------

Native minimega Android launch settings are stored under ``self.vm["android"]``
and emitted as minimega ``vm config android-*`` commands.

Examples include:

* ``android-sdk``
* ``android-emulator``
* ``android-adb``
* ``android-avd``
* ``android-avd-dir``
* ``android-console-base-port``
* ``android-extra-args``
* ``android-no-window``
* ``android-writable-system``

ADB Driver Configuration
------------------------

ADB handler hints are stored under ``self.vm["adb"]``. minimega is authoritative
for the final assigned port values after launch. FIREWHEEL updates the VM
Resource Handler configuration from minimega's actual values before starting the
ADB driver.

Relevant values include:

* ``adb_serial``
* ``android_console_port``
* ``android_adb_port``
* ``require_root``

Default Android Launch Parameters
=================================

The base Android component sets several Android emulator launch defaults so
that Android VMs behave predictably in FIREWHEEL experiments.

By default, it configures:

* ``android-no-window = True`` so emulators launch headless;
* ``android-writable-system = False`` so the system image is not made writable
  unless a workflow explicitly requires it;
* ``android-extra-args`` to include ``-no-metrics``;
* ``android-extra-args`` to include ``-read-only``;
* ``android-extra-args`` to include ``-no-snapshot``,
  ``-no-snapshot-load``, and ``-no-snapshot-save``.

Together, these defaults favor reproducible, non-interactive emulator launches
that can safely reuse a shared AVD definition across multiple phones.

The ``-read-only`` default is especially important when multiple emulators use
one shared AVD. If ``-read-only`` is disabled and multiple phones still point to
that same AVD, emulator launch is expected to fail.

Some advanced workflows may override these defaults. For example, writable
system modifications or persistent per-VM AVD state may require disabling the
shared-AVD ``-read-only`` behavior and using a unique writable AVD directory per
VM.

VM Resources
============

This model component provides core VM resources such as:

* ``configure_ips_android.sh``
* ``fix_routing_rules.sh``
* ``install_apk_android.sh``
* ``set_hostname_android.sh``

It also stages supporting Termux/Bash artifacts used by optional Android-side
Bash installation workflows.

Together, these resources support Android-specific runtime networking, APK
installation, hostname configuration, and optional advanced Bash enablement.

Runtime Network Configuration
=============================

Android network configuration is handled by Android-specific VM resources, not
by Linux distribution mechanisms.

The Android network configuration resources use runtime commands such as:

* ``ip addr``
* ``ip link``
* ``ip route``
* ``ip rule``
* ``setprop``

Network configuration is not persistent across Android reboot. After reboot,
IP addresses, routes, policy routing rules, and firewall rules must be
reconfigured if needed.

The Android network scripts should use:

.. code-block:: sh

   #!/system/bin/sh

and should avoid Bash-specific syntax.

Hostname Configuration
======================

Android hostname behavior varies across Android versions and images. The
Android hostname resource uses a best-effort approach and may try multiple
methods, such as:

* ``setprop net.hostname``
* ``hostname`` if available;
* ``toybox hostname`` if available;
* writing ``/proc/sys/kernel/hostname`` if writable;
* best-effort ``/etc/hosts`` or ``/system/etc/hosts`` updates if writable.

Failure to update ``/etc/hosts`` is common and does not necessarily mean the
hostname configuration failed.

APK Installation
================

The base Android component provides an ``install_apk`` helper through the
``AndroidPhone`` object. APK installation is performed through an Android VM
resource helper that waits for Android boot completion and Package Manager
readiness before invoking ``pm install``.

A complete APK can be installed with:

.. code-block:: python

   phone.install_apk(-50, "my-app.apk")

Multiple independent APKs should be installed as separate APKs. Split APKs
require all required split files and explicit split-install behavior.

Android may report:

.. code-block:: text

   Error: device is still booting.

if APK installation is attempted before the Android framework is ready. The
Android APK installer helper handles this by waiting and retrying readiness
checks before installing.

Bash and Linux Compatibility
============================

Bash is not installed by default. The ADB driver and Android VM resources should
not require Bash.

If Bash is explicitly installed, it should be treated as an advanced optional
feature. Writable-system behavior may be required, and this can interact with
the default shared-AVD ``-read-only`` behavior.

Python is not installed on Android by default. Python-based Linux VM resources
should not be assumed to work on Android.

LinuxHost Compatibility
=======================

This component reuses selected generic Linux/FIREWHEEL behavior through
``LinuxHost`` integration and conflict handlers, so Android model components do
not need to implement every common host capability from scratch.

At the same time, Android is not a traditional Linux distribution, and Android-
specific model components should treat inherited Linux behavior as a useful
starting point rather than as a drop-in match.

The following Linux assumptions do not generally apply to Android:

* ``/root`` as an interactive home directory;
* SSH server availability;
* Bash availability;
* Python availability;
* ``/etc/network/interfaces``;
* ``/etc/sysconfig/network-scripts``;
* NetworkManager;
* systemd;
* ``systemctl``;
* cron.

In practice, Android model components can often reuse generic behavior where it
still fits, while overriding or disabling inherited resources and helpers that
do not apply to Android.

**Model Component Dependencies:**
    * :ref:`base_objects_mc`

Available Objects
=================

.. automodule:: android.base_objects
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :show-inheritance:
    :exclude-members: __dict__,__weakref__,__module__
