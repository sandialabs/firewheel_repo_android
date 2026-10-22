#!/usr/bin/env python3
"""
Host-side FIREWHEEL runner for Maestro Android UI automation.

This script is executed as a host-based VM resource by
VMResourceHandler._run_vm_resource_host().

The runner:

1. resolves Maestro flow resources through VmResourceStore on the execution host,
2. resolves the runtime ADB serial from FIREWHEEL environment/config,
3. validates ADB/device readiness,
4. serializes access to each ADB device using a host-local lock,
5. runs Maestro,
6. writes artifacts under FIREWHEEL's logging root,
7. prints a one-line JSON summary to stdout.

Device resolution order:

    1. FIREWHEEL_ADB_SERIAL,
    2. FIREWHEEL_ANDROID_CONSOLE_PORT -> emulator-<port>,
    3. FIREWHEEL_VM_CONFIG_JSON["adb_serial"],
    4. FIREWHEEL_VM_CONFIG_JSON["android_console_port"] -> emulator-<port>,
    5. fail.

The model component intentionally does not pass a device serial because minimega
is authoritative for final Android port assignment.

By default, a Maestro test failure is recorded in result.json but this runner
exits 0 so the experiment can continue. If --fail-experiment-on-failure is set,
the runner exits with Maestro's nonzero exit code.
"""

import os
import sys
import json
import time
import fcntl
import shlex
import shutil
import argparse
import traceback
import subprocess
from pathlib import Path
from datetime import datetime, timezone

from firewheel.config import config as global_config
from firewheel.lib.experiment_utils import extract_archive_safely
from firewheel.vm_resource_manager.vm_resource_store import VmResourceStore


class DeviceLock:
    """
    Host-local exclusive lock for a resolved ADB device serial.
    """

    def __init__(self, device, lock_root="/tmp/firewheel-maestro-locks"):  # noqa: S108
        """
        Initialize the device lock state.

        Args:
            device (str): Resolved ADB device serial.
            lock_root (str): Host directory used to store per-device lock files.
        """
        safe_device = (
            str(device)
            .replace("/", "_")
            .replace("\\", "_")
            .replace(":", "_")
            .replace(" ", "_")
        )

        self.device = device
        self.lock_dir = Path(lock_root)
        self.lock_path = self.lock_dir / f"{safe_device}.lock"
        self.handle = None
        self.wait_seconds = 0.0

    def __enter__(self):
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self.handle = self.lock_path.open("w", encoding="utf-8")

        start = time.monotonic()
        fcntl.flock(self.handle, fcntl.LOCK_EX)
        self.wait_seconds = time.monotonic() - start

        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(f"pid={os.getpid()}\n")
        self.handle.write(f"device={self.device}\n")
        self.handle.flush()

        return self

    def __exit__(self, exc_type, exc, tb):
        if self.handle:
            fcntl.flock(self.handle, fcntl.LOCK_UN)
            self.handle.close()


def write_text(path, content):
    """
    Write text to a file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(content), encoding="utf-8")


def write_json(path, content):
    """
    Write JSON to a file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2, sort_keys=True), encoding="utf-8")


def command_to_string(args):
    """
    Format argv as a readable shell command.

    Args:
        args (list[str]): Command argv.

    Returns:
        str: Shell-quoted command string.
    """
    return " ".join(shlex.quote(str(arg)) for arg in args)


def get_firewheel_vm_config():
    """
    Read FIREWHEEL_VM_CONFIG_JSON from the environment.

    Returns:
        dict: Decoded FIREWHEEL VM configuration, or an empty dict if unset.

    Raises:
        RuntimeError: If FIREWHEEL_VM_CONFIG_JSON is invalid or not a JSON object.
    """
    raw = os.environ.get("FIREWHEEL_VM_CONFIG_JSON")

    if not raw:
        return {}

    try:
        config = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("FIREWHEEL_VM_CONFIG_JSON is not valid JSON") from exc

    if not isinstance(config, dict):
        raise RuntimeError("FIREWHEEL_VM_CONFIG_JSON must decode to a JSON object")

    return config


def resolve_vm_name(vm_config):
    """
    Resolve VM name from FIREWHEEL runtime metadata.

    Args:
        vm_config (dict): Decoded FIREWHEEL VM configuration.

    Returns:
        str: Resolved FIREWHEEL VM name.

    Raises:
        RuntimeError: If no VM name is available.
    """
    if os.environ.get("FIREWHEEL_VM_NAME"):
        return os.environ["FIREWHEEL_VM_NAME"]

    if vm_config.get("vm_name"):
        return str(vm_config["vm_name"])

    raise RuntimeError(
        "Unable to determine FIREWHEEL VM name. Expected FIREWHEEL_VM_NAME "
        "or FIREWHEEL_VM_CONFIG_JSON containing vm_name."
    )


def resolve_adb_serial(vm_config):
    """
    Resolve the runtime Android ADB serial from FIREWHEEL runtime metadata.

    Args:
        vm_config (dict): Decoded FIREWHEEL VM configuration.

    Returns:
        str: Resolved Android emulator ADB serial.

    Raises:
        RuntimeError: If no Android serial information is available.
    """
    if os.environ.get("FIREWHEEL_ADB_SERIAL"):
        return os.environ["FIREWHEEL_ADB_SERIAL"]

    if os.environ.get("FIREWHEEL_ANDROID_CONSOLE_PORT"):
        return f"emulator-{os.environ['FIREWHEEL_ANDROID_CONSOLE_PORT']}"

    if vm_config.get("adb_serial"):
        return str(vm_config["adb_serial"])

    if vm_config.get("android_console_port") is not None:
        return f"emulator-{vm_config['android_console_port']}"

    raise RuntimeError(
        "Unable to determine Android ADB serial. Expected FIREWHEEL_ADB_SERIAL, "
        "FIREWHEEL_ANDROID_CONSOLE_PORT, or FIREWHEEL_VM_CONFIG_JSON containing "
        "adb_serial/android_console_port."
    )


def require_tool(name):
    """
    Resolve a required executable.

    Args:
        name (str): Executable name or absolute path.

    Returns:
        str: Resolved executable path or original absolute path.

    Raises:
        RuntimeError: If the executable cannot be found.
    """
    if os.path.isabs(name):
        if not Path(name).exists():
            raise RuntimeError(f"Required tool does not exist: {name}")
        return name

    resolved = shutil.which(name)
    if not resolved:
        raise RuntimeError(f"Required tool not found on PATH: {name}")

    return resolved


def make_artifact_dir(args, vm_name, flow_label):
    """
    Create the artifact directory for this run.

    Args:
        args (argparse.Namespace): Parsed runner arguments.
        vm_name (str): FIREWHEEL VM name.
        flow_label (str): Flow label used in the default artifact path.

    Returns:
        pathlib.Path: Created artifact directory path.
    """
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if args.artifact_dir:
        artifact_dir = Path(args.artifact_dir)
    else:
        logging_root = Path(global_config["logging"]["root_dir"]) / Path(
            global_config["logging"]["vmr_log_dir"]
        )

        if args.artifact_subdir:
            base = logging_root / args.artifact_subdir
        else:
            base = logging_root / "maestro" / vm_name / flow_label

        artifact_dir = base / run_id

    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir


def run_text_command(args, output_file, timeout=30):
    """
    Run a diagnostic command and write stdout/stderr/return code to a file.

    Diagnostic failures are recorded but do not raise.

    Args:
        args (list[str]): Command argv.
        output_file (str | pathlib.Path): Output file to write.
        timeout (int): Command timeout in seconds.

    Returns:
        int: Command return code, or ``1`` if command execution itself fails.
    """
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        write_text(
            output_file,
            "\n".join(
                [
                    f"$ {command_to_string(args)}",
                    f"returncode={result.returncode}",
                    "",
                    "STDOUT:",
                    result.stdout or "",
                    "",
                    "STDERR:",
                    result.stderr or "",
                ]
            ),
        )

        return result.returncode

    except Exception as exc:  # noqa: BLE001
        write_text(
            output_file,
            f"$ {command_to_string(args)}\nERROR: {type(exc).__name__}: {exc}\n",
        )
        return 1


def run_stdout_bytes_to_file(args, output_file, timeout=30):
    """
    Run a command and write stdout bytes to a file.

    Used for adb screencap.

    Args:
        args (list[str]): Command argv.
        output_file (str | pathlib.Path): Output file to write.
        timeout (int): Command timeout in seconds.

    Returns:
        int: Command return code, or ``1`` if command execution itself fails.
    """
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    stderr_file = output_file.with_suffix(output_file.suffix + ".stderr.txt")

    try:
        with output_file.open("wb") as stdout_handle:
            result = subprocess.run(
                args,
                stdout=stdout_handle,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )

        stderr_file.write_bytes(result.stderr or b"")
        return result.returncode

    except Exception as exc:  # noqa: BLE001
        write_text(
            stderr_file,
            f"$ {command_to_string(args)}\nERROR: {type(exc).__name__}: {exc}\n",
        )
        return 1


def validate_adb_device(adb_binary, device, artifact_dir):
    """
    Ensure the resolved ADB device exists and Android boot has completed.

    Args:
        adb_binary (str): ADB executable path.
        device (str): Resolved Android emulator ADB serial.
        artifact_dir (str | pathlib.Path): Artifact directory for diagnostics.

    Raises:
        RuntimeError: If the resolved ADB device is not online or Android boot is
            incomplete.
    """
    run_text_command(
        [adb_binary, "devices"],
        artifact_dir / "adb_devices.txt",
    )

    subprocess.run(
        [adb_binary, "-s", device, "wait-for-device"],
        check=True,
    )

    state = subprocess.run(
        [adb_binary, "-s", device, "get-state"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    if state != "device":
        raise RuntimeError(f"ADB device {device!r} is not online; state={state!r}")

    boot_completed = subprocess.run(
        [adb_binary, "-s", device, "shell", "getprop", "sys.boot_completed"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    if boot_completed != "1":
        raise RuntimeError(
            f"ADB device {device!r} is online but Android boot is incomplete; "
            f"sys.boot_completed={boot_completed!r}"
        )


def capture_device_state(adb_binary, device, artifact_dir, prefix):
    """
    Capture useful before/after device state.
    """
    run_text_command(
        [adb_binary, "-s", device, "shell", "getprop"],
        artifact_dir / f"{prefix}_getprop.txt",
        timeout=60,
    )

    run_text_command(
        [adb_binary, "-s", device, "shell", "dumpsys", "window"],
        artifact_dir / f"{prefix}_window.txt",
        timeout=60,
    )

    run_stdout_bytes_to_file(
        [adb_binary, "-s", device, "exec-out", "screencap", "-p"],
        artifact_dir / f"{prefix}_screenshot.png",
        timeout=60,
    )


def resolve_flow_path(args, artifact_dir):
    """
    Resolve the local Maestro flow path using VmResourceStore.

    Args:
        args (argparse.Namespace): Parsed runner arguments.
        artifact_dir (str | pathlib.Path): Artifact directory for copied flow
            inputs.

    Returns:
        tuple[pathlib.Path, str]: Local path to the Maestro YAML file and
            artifact label derived from the flow.

    Raises:
        FileNotFoundError: If the requested flow resource, bundle resource, or
            bundle entrypoint cannot be found.
        RuntimeError: If the bundle entrypoint resolves outside the extraction
            directory.
    """
    store = VmResourceStore()

    if args.flow_resource:
        flow_path = Path(store.get_path(args.flow_resource)).resolve()

        if not flow_path.exists():
            raise FileNotFoundError(
                f"Flow resource {args.flow_resource!r} resolved to missing path "
                f"{flow_path}"
            )

        shutil.copy2(flow_path, artifact_dir / "flow.yaml")
        return flow_path, Path(args.flow_resource).stem

    bundle_path = Path(store.get_path(args.flow_bundle_resource)).resolve()

    if not bundle_path.exists():
        raise FileNotFoundError(
            f"Flow bundle resource {args.flow_bundle_resource!r} resolved to "
            f"missing path {bundle_path}"
        )

    shutil.copy2(bundle_path, artifact_dir / bundle_path.name)

    bundle_workdir = artifact_dir / "bundle_workdir"
    extract_archive_safely(bundle_path, bundle_workdir)

    flow_path = (bundle_workdir / args.entrypoint).resolve()

    try:
        flow_path.relative_to(bundle_workdir.resolve())
    except ValueError as exc:
        raise RuntimeError(
            f"Bundle entrypoint escapes extraction directory: {args.entrypoint}"
        ) from exc

    if not flow_path.exists():
        raise FileNotFoundError(
            f"Bundle entrypoint {args.entrypoint!r} not found in "
            f"{args.flow_bundle_resource!r}"
        )

    shutil.copy2(flow_path, artifact_dir / "flow.yaml")
    return flow_path, Path(args.entrypoint).stem


def run_maestro(maestro_binary, device, flow_path, artifact_dir, timeout):
    """
    Run Maestro and write stdout/stderr/exit-code artifacts.

    Args:
        maestro_binary (str): Maestro executable path.
        device (str): Resolved Android emulator ADB serial.
        flow_path (str | pathlib.Path): Local Maestro flow path.
        artifact_dir (str | pathlib.Path): Artifact directory for runner output.
        timeout (int): Maestro command timeout in seconds.

    Returns:
        tuple[int, bool]: Maestro exit code and timeout flag.
    """
    command = [
        maestro_binary,
        "--device",
        device,
        "test",
        str(flow_path),
    ]
    print(artifact_dir)

    write_text(artifact_dir / "command.txt", command_to_string(command) + "\n")
    write_json(artifact_dir / "command.json", command)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        write_text(artifact_dir / "maestro_stdout.txt", result.stdout or "")
        write_text(artifact_dir / "maestro_stderr.txt", result.stderr or "")
        write_text(artifact_dir / "exit_code.txt", f"{result.returncode}\n")

        return result.returncode, False

    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")

        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")

        stderr += f"\nMaestro timed out after {timeout} seconds.\n"

        write_text(artifact_dir / "maestro_stdout.txt", stdout)
        write_text(artifact_dir / "maestro_stderr.txt", stderr)
        write_text(artifact_dir / "exit_code.txt", "124\n")

        return 124, True


def parse_args(argv):
    """
    Parse command-line arguments.

    Args:
        argv (list[str]): Command-line arguments excluding program name.

    Returns:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Run a Maestro flow as a FIREWHEEL host-based VM resource."
    )

    flow_group = parser.add_mutually_exclusive_group(required=True)
    flow_group.add_argument(
        "--flow-resource",
        help="Single Maestro YAML file resource name in VmResourceStore.",
    )
    flow_group.add_argument(
        "--flow-bundle-resource",
        help="Tar archive resource name in VmResourceStore containing Maestro flows.",
    )

    parser.add_argument(
        "--entrypoint",
        help="Path inside --flow-bundle-resource to the Maestro YAML file.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout for the Maestro command in seconds.",
    )
    parser.add_argument(
        "--artifact-dir",
        help="Exact artifact output directory.",
    )
    parser.add_argument(
        "--artifact-subdir",
        help="Subdirectory under FIREWHEEL logging.root_dir for artifacts.",
    )
    parser.add_argument(
        "--fail-experiment-on-failure",
        action="store_true",
        help="Exit nonzero if Maestro exits nonzero.",
    )
    parser.add_argument(
        "--adb-binary",
        default="adb",
        help="ADB executable. Defaults to adb on PATH.",
    )
    parser.add_argument(
        "--maestro-binary",
        default="maestro",
        help="Maestro executable. Defaults to maestro on PATH.",
    )

    args = parser.parse_args(argv)

    if args.flow_bundle_resource and not args.entrypoint:
        parser.error("--entrypoint is required with --flow-bundle-resource")

    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    return args


def main(argv=None):
    """
    Main program.

    Args:
        argv (list[str] | None): Optional command-line arguments excluding
            program name.

    Returns:
        int: Runner process exit code.
    """
    if argv is None:
        argv = sys.argv[1:]

    args = parse_args(argv)

    artifact_dir = None
    start_time_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    start_monotonic = time.monotonic()

    try:
        vm_config = get_firewheel_vm_config()
        vm_name = resolve_vm_name(vm_config)
        adb_binary = require_tool(args.adb_binary)
        maestro_binary = require_tool(args.maestro_binary)
        device = resolve_adb_serial(vm_config)

        print(vm_config)
        # The flow label is needed for the default artifact path, but resolving
        # the actual local flow path also needs the artifact directory. Therefore
        # derive the label from the resource/entrypoint first.
        if args.flow_resource:
            flow_label = Path(args.flow_resource).stem
        else:
            flow_label = Path(args.entrypoint).stem

        artifact_dir = make_artifact_dir(args, vm_name, flow_label)
        print(artifact_dir)

        write_json(
            artifact_dir / "runner_input.json",
            {
                "argv": argv,
                "vm_name": vm_name,
                "flow_resource": args.flow_resource,
                "flow_bundle_resource": args.flow_bundle_resource,
                "entrypoint": args.entrypoint,
                "start_time_utc": start_time_utc,
                "environment_summary": {
                    "FIREWHEEL_VM_NAME": os.environ.get("FIREWHEEL_VM_NAME"),
                    "FIREWHEEL_VM_UUID": os.environ.get("FIREWHEEL_VM_UUID"),
                    "FIREWHEEL_VM_ENGINE": os.environ.get("FIREWHEEL_VM_ENGINE"),
                    "FIREWHEEL_ADB_SERIAL": os.environ.get("FIREWHEEL_ADB_SERIAL"),
                    "FIREWHEEL_ANDROID_CONSOLE_PORT": os.environ.get(
                        "FIREWHEEL_ANDROID_CONSOLE_PORT"
                    ),
                    "FIREWHEEL_ANDROID_ADB_PORT": os.environ.get(
                        "FIREWHEEL_ANDROID_ADB_PORT"
                    ),
                },
                "vm_config_summary": {
                    "vm_name": vm_config.get("vm_name"),
                    "vm_uuid": vm_config.get("vm_uuid"),
                    "engine": vm_config.get("engine"),
                    "adb_serial": vm_config.get("adb_serial"),
                    "android_console_port": vm_config.get("android_console_port"),
                    "android_adb_port": vm_config.get("android_adb_port"),
                },
            },
        )

        run_text_command([adb_binary, "version"], artifact_dir / "adb_version.txt")
        run_text_command(
            [maestro_binary, "--version"],
            artifact_dir / "maestro_version.txt",
        )

        write_text(artifact_dir / "resolved_device.txt", device + "\n")

        validate_adb_device(adb_binary, device, artifact_dir)

        flow_path, flow_label = resolve_flow_path(args, artifact_dir)

        write_json(
            artifact_dir / "resolved_paths.json",
            {
                "artifact_dir": str(artifact_dir),
                "flow_path": str(flow_path),
                "flow_label": flow_label,
            },
        )

        with DeviceLock(device) as device_lock:
            capture_device_state(adb_binary, device, artifact_dir, "before")

            maestro_exit_code, timed_out = run_maestro(
                maestro_binary=maestro_binary,
                device=device,
                flow_path=flow_path,
                artifact_dir=artifact_dir,
                timeout=args.timeout,
            )

            capture_device_state(adb_binary, device, artifact_dir, "after")

            lock_metadata = {
                "enabled": True,
                "device": device,
                "lock_path": str(device_lock.lock_path),
                "wait_seconds": device_lock.wait_seconds,
            }

        end_time_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        duration_seconds = time.monotonic() - start_monotonic

        status = "pass" if maestro_exit_code == 0 else "fail"

        runner_exit_code = 0
        if maestro_exit_code != 0 and args.fail_experiment_on_failure:
            runner_exit_code = maestro_exit_code

        result = {
            "tool": "maestro",
            "status": status,
            "timed_out": timed_out,
            "vm_name": vm_name,
            "flow_label": flow_label,
            "flow_resource": args.flow_resource,
            "flow_bundle_resource": args.flow_bundle_resource,
            "entrypoint": args.entrypoint,
            "device": device,
            "maestro_exit_code": maestro_exit_code,
            "runner_exit_code": runner_exit_code,
            "fail_experiment_on_failure": args.fail_experiment_on_failure,
            "start_time_utc": start_time_utc,
            "end_time_utc": end_time_utc,
            "duration_seconds": duration_seconds,
            "device_lock": lock_metadata,
            "artifacts": {
                "runner_input": "runner_input.json",
                "resolved_device": "resolved_device.txt",
                "resolved_paths": "resolved_paths.json",
                "command": "command.txt",
                "command_json": "command.json",
                "stdout": "maestro_stdout.txt",
                "stderr": "maestro_stderr.txt",
                "exit_code": "exit_code.txt",
                "flow": "flow.yaml",
                "adb_devices": "adb_devices.txt",
                "before_screenshot": "before_screenshot.png",
                "after_screenshot": "after_screenshot.png",
                "before_window": "before_window.txt",
                "after_window": "after_window.txt",
            },
        }

        write_json(artifact_dir / "result.json", result)

        # Print one-line JSON so VMResourceHandler logs get a concise summary.
        print(json.dumps(result, sort_keys=True))

        return runner_exit_code

    except Exception as exc:  # noqa: BLE001
        end_time_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        duration_seconds = time.monotonic() - start_monotonic
        error_text = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )

        if artifact_dir:
            write_text(artifact_dir / "runner_error.txt", error_text)
            write_json(
                artifact_dir / "result.json",
                {
                    "tool": "maestro",
                    "status": "runner_error",
                    "runner_exit_code": 2,
                    "maestro_exit_code": None,
                    "start_time_utc": start_time_utc,
                    "end_time_utc": end_time_utc,
                    "duration_seconds": duration_seconds,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )

        print(error_text, file=sys.stderr)

        return 2


if __name__ == "__main__":
    sys.exit(main())
