"""
Model component objects for Android Maestro automation.

This model component provides a host-side FIREWHEEL integration for Maestro.
Maestro flows are distributed as normal FIREWHEEL VM resources and executed on
the physical/minimega host by a host-based VM resource runner.

The runner resolves flow resources via VmResourceStore on the host where it
executes, then invokes:

    maestro --device <runtime-adb-serial> test <flow.yaml>

Important:
    This model component intentionally does not pass an ADB serial to the runner.

    The Android ADB serial is runtime state. The model component may request a
    console base port, but minimega is authoritative for the final assigned
    Android console/ADB ports. Therefore, firewheel_maestro_runner.py resolves
    the actual device serial at runtime from FIREWHEEL host-runner environment
    variables such as FIREWHEEL_VM_CONFIG_JSON.
"""

import shlex

from base_objects import RunHostExecutableScheduleEntry
from android.base_objects import AndroidPhone

from firewheel.control.experiment_graph import require_class


@require_class(AndroidPhone)
class AndroidMaestroEndpoint:
    """
    Decorator object that adds Maestro automation helpers to an Android VM.

    Expected usage:

        phone.decorate(AndroidPhone)
        phone.decorate(AndroidPixel9a)
        phone.decorate(AndroidMaestroEndpoint)

        phone.add_maestro_flow(
            start_time=30,
            flow_resource="settings_smoke.yaml",
        )

    The associated ScheduleEntry runs on the host, not inside the Android guest.
    """

    MAESTRO_RUNNER_RESOURCE = "firewheel_maestro_runner.py"

    def __init__(self):
        """
        Initialize Maestro metadata on the decorated Android VM object.
        """
        self.maestro_flows = getattr(self, "maestro_flows", [])

    def _create_maestro_entry(self, start_time, runner_args, resources):
        """
        Create and register a host-side ScheduleEntry for the Maestro runner.

        Args:
            start_time (int): FIREWHEEL schedule time.
            runner_args (list[str]): Arguments for firewheel_maestro_runner.py.
            resources (list[str]): Additional VM resources needed by the runner,
                such as flow YAML files or flow bundles.

        Returns:
            RunHostExecutableScheduleEntry: The created schedule entry.

        Raises:
            TypeError: If the decorated object does not provide
                ``vm_resource_schedule``.
        """
        if not hasattr(self, "vm_resource_schedule"):
            raise TypeError(
                "AndroidMaestroEndpoint requires vm_resource_schedule. "
                "Decorate the vertex with AndroidPhone first."
            )

        # ScheduleEntry currently stores list arguments by joining them with spaces.
        # VMResourceHandler later reconstructs argv with shlex.split().
        quoted_args = [shlex.quote(str(arg)) for arg in runner_args]

        entry = RunHostExecutableScheduleEntry(
            start_time,
            self.MAESTRO_RUNNER_RESOURCE,
            quoted_args,
        )

        # Make the host-side runner available through VmResourceStore.
        entry.add_file(
            self.MAESTRO_RUNNER_RESOURCE,
            self.MAESTRO_RUNNER_RESOURCE,
            executable=True,
        )

        # Make user-provided flow assets available through VmResourceStore.
        for resource in dict.fromkeys(resources):
            entry.add_file(
                resource,
                resource,
                executable=False,
            )

        self.vm_resource_schedule.add_vm_resource(entry)

        return entry

    def add_maestro_flow(
        self,
        start_time,
        flow_resource,
        timeout=120,
        artifact_subdir=None,
        fail_experiment_on_failure=False,
    ):
        """
        Schedule a single Maestro YAML flow to run against this Android VM.

        Args:
            start_time (int): FIREWHEEL schedule time.
            flow_resource (str): Name of the Maestro YAML file in VmResourceStore.
                This file must be listed as a VM resource in a model component
                MANIFEST.
            timeout (int): Runner/Maestro timeout in seconds.
            artifact_subdir (str): Optional artifact subdirectory under
                FIREWHEEL logging root.
            fail_experiment_on_failure (bool): If True, Maestro test failure causes
                the host VM resource to exit nonzero. If False, failures are
                recorded in result.json but the host VM resource exits 0.

        Returns:
            RunHostExecutableScheduleEntry: The created schedule entry.
        """
        runner_args = [
            "--flow-resource",
            flow_resource,
            "--timeout",
            str(int(timeout)),
        ]

        if artifact_subdir:
            runner_args.extend(["--artifact-subdir", artifact_subdir])

        if fail_experiment_on_failure:
            runner_args.append("--fail-experiment-on-failure")

        entry = self._create_maestro_entry(
            start_time=start_time,
            runner_args=runner_args,
            resources=[flow_resource],
        )

        self.maestro_flows.append(
            {
                "type": "single",
                "flow_resource": flow_resource,
                "start_time": start_time,
                "timeout": int(timeout),
                "artifact_subdir": artifact_subdir,
                "fail_experiment_on_failure": bool(fail_experiment_on_failure),
            }
        )

        return entry

    def add_maestro_flow_bundle(
        self,
        start_time,
        bundle_resource,
        entrypoint,
        timeout=120,
        artifact_subdir=None,
        fail_experiment_on_failure=False,
    ):
        """
        Schedule a Maestro flow from a bundled archive.

        This is the recommended mode for nontrivial workflows because Maestro
        flows may reference other files relative to the entrypoint.

        Args:
            start_time (int): FIREWHEEL schedule time.
            bundle_resource (str): Name of the archive in VmResourceStore.
                This archive must be listed as a VM resource in a model component
                MANIFEST.
            entrypoint (str): Path inside the extracted bundle to the flow YAML.
                Example: flows/settings_smoke.yaml.
            timeout (int): Runner/Maestro timeout in seconds.
            artifact_subdir (str): Optional artifact subdirectory under FIREWHEEL
                logging root.
            fail_experiment_on_failure (bool): If True, Maestro failure exits
                the host VM resource nonzero.

        Returns:
            RunHostExecutableScheduleEntry: The created schedule entry.
        """
        runner_args = [
            "--flow-bundle-resource",
            bundle_resource,
            "--entrypoint",
            entrypoint,
            "--timeout",
            str(int(timeout)),
        ]

        if artifact_subdir:
            runner_args.extend(["--artifact-subdir", artifact_subdir])

        if fail_experiment_on_failure:
            runner_args.append("--fail-experiment-on-failure")

        entry = self._create_maestro_entry(
            start_time=start_time,
            runner_args=runner_args,
            resources=[bundle_resource],
        )

        self.maestro_flows.append(
            {
                "type": "bundle",
                "bundle_resource": bundle_resource,
                "entrypoint": entrypoint,
                "start_time": start_time,
                "timeout": int(timeout),
                "artifact_subdir": artifact_subdir,
                "fail_experiment_on_failure": bool(fail_experiment_on_failure),
            }
        )

        return entry
