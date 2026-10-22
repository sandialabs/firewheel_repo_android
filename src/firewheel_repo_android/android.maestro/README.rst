.. _android.maestro_mc:

###############
android.maestro
###############

The ``android.maestro`` model component adds host-side `Maestro <https://maestro.mobile.dev/>`_
Android UI automation support for FIREWHEEL Android experiments.

For a full end-to-end workflow example, see the published `Android automation
tutorial <https://sandialabs.github.io/firewheel/tutorials/android/android_app_automation.html>`_.

Maestro is **not** installed inside the Android guest. FIREWHEEL stages the
runner and the flow files as VM resources, then executes the runner on the
physical host that owns the Android VM.

**Model Component Dependencies:**
    * :ref:`base_objects_mc`
    * :ref:`android.base_objects_mc`

Overview
========

This model component provides ``AndroidMaestroEndpoint``, which adds host-side
Maestro scheduling helpers to an Android VM object.

At runtime, the host-side runner:

#. resolves the flow resource through ``VmResourceStore``;
#. resolves the Android emulator's runtime ADB serial from VM Resource Handler
   metadata;
#. validates device readiness and waits for Android boot completion;
#. acquires a host-local per-device lock;
#. runs ``maestro --device <serial> test <flow.yaml>``;
#. captures artifacts including stdout, stderr, screenshots, and
   ``result.json``.

The per-device lock prevents two Maestro flows on the same host from driving the
same emulator at the same time.

Runtime ADB Serial Resolution
=============================

This model component intentionally does **not** pass a fixed ADB serial to the
Maestro runner.

Android emulator ADB serials are runtime values. A model component may request a
console base port, but minimega is authoritative for the final assigned Android
console and ADB ports. The runner therefore resolves the device at runtime using
VM Resource Handler metadata.

Resolution order:

#. ``FIREWHEEL_ADB_SERIAL``
#. ``FIREWHEEL_ANDROID_CONSOLE_PORT`` converted to ``emulator-<port>``
#. ``FIREWHEEL_VM_CONFIG_JSON["adb_serial"]``
#. ``FIREWHEEL_VM_CONFIG_JSON["android_console_port"]`` converted to ``emulator-<port>``

If none of these values are available, the runner fails rather than guessing.
This avoids accidentally driving the wrong Android emulator in multi-device
experiments.

Installation
============

This model component includes an ``INSTALL`` workflow to provision Maestro on
hosts that may run Android emulator VMs.

The INSTALL workflow installs Java 17+, downloads and verifies a pinned Maestro
CLI ZIP, extracts it into a model-component-local directory, creates a
non-interactive ``maestro`` wrapper in the default supported location
``/usr/local/bin/maestro``, and verifies both ``maestro`` and ``adb``.

Flow Resources
==============

Maestro flows are host-side FIREWHEEL VM resources.

Any flow file or flow bundle passed to ``add_maestro_flow()`` or
``add_maestro_flow_bundle()`` must be available through the VM resource system.
In practice, this means the flow file or bundle must be listed as a VM resource
by a model component ``MANIFEST``.

This model component includes example flows under ``vm_resources/examples/``:

``settings_check.yaml``
    Basic Settings application check.

``settings_network.yaml``
    Navigates into network-related Settings pages and verifies expected UI state.

``settings_search.yaml``
    Exercises text input by using Settings search.

``expected_failure.yaml``
    A deliberately failing flow for validating failure handling and artifacts.

For runnable examples using these flows, see :ref:`android.maestro_test_topology_mc`.

Usage
=====

A typical Android phone model component can be decorated with
``AndroidMaestroEndpoint``.

.. code-block:: python

   from firewheel.control.experiment_graph import Vertex

   from android.maestro import AndroidMaestroEndpoint


   def build_graph(g):
       phone = Vertex(g, "phone0")

       phone.decorate(AndroidMaestroEndpoint)

       phone.add_maestro_flow(
           start_time=10,
           flow_resource="examples/settings_check.yaml",
           timeout=120,
       )

       return g

The scheduled Maestro flow runs on the host at experiment time, targeting the
runtime Android emulator associated with ``phone0``.

Parameters
==========

``add_maestro_flow(...)``
    Schedule a single Maestro YAML flow.

    Key parameters:

    ``start_time``
        FIREWHEEL schedule time.

    ``flow_resource``
        Name of the Maestro YAML VM resource.

    ``timeout``
        Maximum time, in seconds, to allow the Maestro command to run.

    ``artifact_subdir``
        Optional subdirectory under FIREWHEEL's logging root for artifacts.

    ``fail_experiment_on_failure``
        If ``True``, a Maestro failure causes the host-based VM resource to exit
        nonzero. If ``False``, the failure is recorded in ``result.json`` but
        the runner exits zero so the experiment can continue.

``add_maestro_flow_bundle(...)``
    Schedule a Maestro flow from a bundled archive.

    This is the recommended mode for nontrivial workflows because Maestro flows
    may reference other files relative to the entrypoint.

    Key parameters:

    ``start_time``
        FIREWHEEL schedule time.

    ``bundle_resource``
        Name of the archive VM resource.

    ``entrypoint``
        Path inside the extracted bundle to the flow YAML.

    ``timeout``
        Maximum time, in seconds, to allow the Maestro command to run.

    ``artifact_subdir``
        Optional subdirectory under FIREWHEEL's logging root for artifacts.

    ``fail_experiment_on_failure``
        If ``True``, a Maestro failure causes the host-based VM resource to exit
        nonzero. If ``False``, the failure is recorded in ``result.json`` but
        the runner exits zero so the experiment can continue.

Bundle Example
==============

Use ``add_maestro_flow_bundle()`` when a Maestro workflow consists of multiple
files.

.. code-block:: text

   maestro_flows/
   ├── flows/
   │   ├── settings_check.yaml
   │   └── settings_network.yaml
   └── data/
       └── sample_text.txt

.. code-block:: bash

   tar czf maestro_flows.tgz maestro_flows/

.. code-block:: python

   phone.add_maestro_flow_bundle(
       start_time=10,
       bundle_resource="maestro_flows.tgz",
       entrypoint="maestro_flows/flows/settings_check.yaml",
       timeout=120,
   )

The runner extracts the bundle into the per-run artifact directory and executes
the selected entrypoint.

Artifacts and Results
=====================

By default, runner artifacts are written under FIREWHEEL's VM Resource log
directory:

.. code-block:: text

   <logging.root_dir>/<logging.vmr_log_dir>/maestro/<vm-name>/<flow-label>/<timestamp>/

The most important file is ``result.json``. It contains a machine-readable
summary of the run, including the VM name, resolved ADB serial, flow resource or
bundle entrypoint, exit codes, pass/fail status, run timestamps, and artifact
references.

Troubleshooting
===============

For general Android launch, ADB, and runtime troubleshooting, see
:ref:`android.base_objects_mc` and :ref:`firewheel_repo_android <android_mc_repo>`.

For Maestro-specific issues, check:

* ``which maestro`` and ``maestro --help`` to confirm the CLI wrapper is
  installed;
* ``java -version`` to confirm Java 17 or newer is available;
* ``minimega -e ".columns name,type,state,android_console_port,android_adb_port,android_serial vm info"``
  if the runner cannot resolve a runtime Android device;
* the relevant model component ``MANIFEST`` if ``VmResourceStore`` cannot find a
  flow resource or bundle.

Best Practices
==============

* Prefer text or accessibility selectors over coordinate taps.
* Keep simple smoke-test flows separate from application-specific workflows.
* Use bundles for workflows that need multiple YAML files or relative assets.
* Do not assume a specific ADB serial in model component code.
* Avoid ``fail_experiment_on_failure=True`` unless the experiment should fail
  when the UI check fails.
* Include screenshots and ``result.json`` in experiment review artifacts.

*****************
Available Objects
*****************

.. automodule:: android.maestro
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :show-inheritance:
    :exclude-members: __dict__,__weakref__,__module__
