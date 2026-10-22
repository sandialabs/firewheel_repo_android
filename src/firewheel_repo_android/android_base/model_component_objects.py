"""This module contains all necessary Model Component Objects for android.base_objects."""

import os
import shlex
from pathlib import Path

from base_objects import VMEndpoint
from linux.base_objects import LinuxHost

from firewheel.control.experiment_graph import (
    IncorrectConflictHandlerError,
    require_class,
)


def android_linuxhost_conflict_handler(
    entry_name,
    _decorator_value,
    _current_instance_value,
):
    """
    The conflict handler for functions overwritten in AndroidPhone that are
    also implemented in LinuxHost, i.e. the ``set_hostname`` function.

    Args:
        entry_name (str): A string describing the attribute that has a conflict
        _decorator_value (any): The value of the attribute from the class that it is trying to be decorated by
        _current_instance_value (any): The current value of the conflicting attribute

    Returns:
        function: A function to be used as the replacement function for Android hosts

    Raises:
        IncorrectConflictHandlerError: If the conflicting function does not exist.
    """
    if entry_name == "set_hostname":
        return AndroidPhone.set_hostname

    if entry_name == "add_root_profiles":
        return AndroidPhone.add_root_profiles

    if entry_name == "configure_ips":
        return AndroidPhone.configure_ips

    raise IncorrectConflictHandlerError


@require_class(VMEndpoint)
@require_class(LinuxHost, conflict_handler=android_linuxhost_conflict_handler)
class AndroidPhone:
    """Base class for an Android phone that implements functionality common to all Android phones."""

    # Static variable for requesting Android emulator console port numbers.
    #
    # Android emulator instances use an even-numbered console port and an ADB
    # daemon port one greater than the console port. For example:
    #
    #   console port: 5554
    #   ADB port:     5555
    #   ADB serial:   emulator-5554
    #
    # FIREWHEEL provides this as a requested base port to minimega through
    # ``android-console-base-port``. minimega is authoritative for the actual
    # assigned ports and may choose a different available pair.
    android_console_base_port = 5554

    # Static variable to determine whether the avd directory has been cleaned
    # from the previous run
    avd_cleaned = False

    def __init__(self):
        """
        Initializes the device as an Android phone.

        This configures two related but distinct pieces of state:

        * Native minimega Android launch settings in ``self.vm["android"]``.
          These are translated into minimega ``vm config android-*`` commands.

        * FIREWHEEL VM Resource Handler ADB settings in ``self.vm["adb"]``.
          These are used by the ADB driver after minimega launches the Android VM.
          minimega's actual post-launch ``android_serial`` and port values are
          authoritative and should overwrite any pre-launch hints.
        """
        self.android_console_base_port = None

        self.current_file_dir = os.path.dirname(__file__)
        self._verify_setup()
        self._cleanup_avd()
        self._setup_launch_config()
        self._preconfigure_networking()

    def _verify_setup(self):
        """
        Ensure required Android INSTALL artifacts are present.

        The android.base_objects INSTALL workflow prepares the model-component-
        local ``Android`` and ``.android`` directories used at experiment build
        and launch time. These may be created directly by INSTALL tasks or by
        extracting optional offline/cache archives such as ``Android.tgz`` and
        ``dot-android.tgz``.

        Raises:
            RuntimeError: If the required Android INSTALL outputs are missing.
        """
        android_home = os.path.join(self.current_file_dir, ".android")
        android_sdk_dir = os.path.join(self.current_file_dir, "Android")

        missing_paths = []
        if not os.path.exists(android_home):
            missing_paths.append(".android")
        if not os.path.exists(android_sdk_dir):
            missing_paths.append("Android")

        if missing_paths:
            missing_text = ", ".join(missing_paths)
            raise RuntimeError(
                "Missing required android.base_objects INSTALL output(s): "
                f"{missing_text}. Run the android.base_objects INSTALL workflow "
                "to provision the local Android environment. Optional offline "
                "archives such as Android.tgz and dot-android.tgz are handled "
                "by INSTALL when provided."
            )

    def _cleanup_avd(self):
        """
        Ensure the .android/avd directory exists.

        Historically this method removed everything under .android/avd before
        each experiment graph build. That is unsafe for Android emulator AVDs
        because emulator runtime state may be created by minimega/emulator with
        ownership or permissions that the FIREWHEEL user cannot later remove.

        The staged AVD directory should be treated as a reusable model-component
        asset. Individual phone model components are responsible for staging
        their AVD if it is missing.

        Clean boot behavior should be handled with emulator flags such as:

            -no-snapshot
            -no-snapshot-load
            -no-snapshot-save

        not by deleting the AVD tree during graph construction.
        """
        if AndroidPhone.avd_cleaned:
            return

        avd_path = Path(self.current_file_dir) / ".android" / "avd"
        avd_path.mkdir(parents=True, exist_ok=True)

        AndroidPhone.avd_cleaned = True

    def _validate_avd_ini(self, avd):
        """
        Validate the staged AVD ini points to the .android/avd layout expected by
        minimega's android-avd-dir setting.

        Args:
            avd (str): Android Virtual Device name.

        Raises:
            RuntimeError: If the AVD ini or AVD directory is missing, or if the
                ini file does not reference the expected staged paths.
        """
        avd_ini = Path(self.current_file_dir) / ".android" / "avd" / f"{avd}.ini"
        avd_dir = Path(self.current_file_dir) / ".android" / "avd" / f"{avd}.avd"

        if not avd_ini.exists():
            raise RuntimeError(f"Missing Android AVD ini file: {avd_ini}")

        if not avd_dir.exists():
            raise RuntimeError(f"Missing Android AVD directory: {avd_dir}")

        text = avd_ini.read_text(encoding="utf-8")
        expected_path = f"path={avd_dir}"

        if expected_path not in text:
            raise RuntimeError(
                f"Android AVD ini {avd_ini} does not contain expected path line "
                f"{expected_path!r}. Contents:\n{text}"
            )

        expected_rel = f"path.rel=avd/{avd}.avd"

        if expected_rel not in text:
            raise RuntimeError(
                f"Android AVD ini {avd_ini} does not contain expected relative path "
                f"line {expected_rel!r}. Contents:\n{text}"
            )

    def _allocate_requested_console_port(self):
        """
        Allocate the next requested Android emulator console base port.

        Returns:
            int: Requested Android emulator console base port.

        Note:
            This is a request/hint to minimega. minimega performs the actual
            reservation at launch time and may assign a different available
            console/ADB port pair.
        """
        requested_port = AndroidPhone.android_console_base_port
        AndroidPhone.android_console_base_port += 2

        self.android_console_base_port = requested_port

        return requested_port

    def _configure_android_sdk_paths(self, android_config):
        """
        Configure default host-side Android SDK, emulator, and adb paths.

        Args:
            android_config (dict): The native minimega Android configuration dictionary.

        Raises:
            RuntimeError: If the Android SDK root, emulator binary, or adb binary
                cannot be found.

        Note:
            These paths are interpreted on the minimega host. They are not VM
            resource files and are not served from the minimega file store.

            Supported extracted SDK layouts include both:

                <android_base>/Android/Sdk/emulator/emulator

            and:

                <android_base>/Android/emulator/emulator
        """
        android_bundle_path = os.path.join(self.current_file_dir, "Android")

        # If a caller/model component explicitly provided android-sdk, honor it.
        explicit_sdk_path = android_config.get("android-sdk")

        sdk_candidates = []
        if explicit_sdk_path:
            sdk_candidates.append(explicit_sdk_path)

        sdk_candidates.extend(
            [
                os.path.join(android_bundle_path, "Sdk"),
                android_bundle_path,
            ]
        )

        sdk_path = None
        for candidate in sdk_candidates:
            emulator_candidate = os.path.join(candidate, "emulator", "emulator")
            adb_candidate = os.path.join(candidate, "platform-tools", "adb")

            if os.path.exists(emulator_candidate) and os.path.exists(adb_candidate):
                sdk_path = candidate
                break

        if sdk_path is None:
            raise RuntimeError(
                "Unable to find a valid Android SDK root. Checked SDK candidates: "
                f"{sdk_candidates}. Expected each valid SDK root to contain "
                "'emulator/emulator' and 'platform-tools/adb'."
            )

        android_config["android-sdk"] = sdk_path

        if not android_config.get("android-emulator"):
            emulator_path = os.path.join(sdk_path, "emulator", "emulator")
            if not os.path.exists(emulator_path):
                raise RuntimeError(
                    f"Unable to find Android emulator binary at {emulator_path}"
                )
            android_config["android-emulator"] = emulator_path

        if not android_config.get("android-adb"):
            adb_path = os.path.join(sdk_path, "platform-tools", "adb")
            if not os.path.exists(adb_path):
                raise RuntimeError(f"Unable to find Android adb binary at {adb_path}")
            android_config["android-adb"] = adb_path

    def _setup_launch_config(self):
        """
        Configure native minimega Android launch settings and ADB handler settings.

        This replaces the previous wrapper-script based launch configuration.
        minimega now launches Android VMs directly using its native ``android``
        VM type and ``vm config android-*`` settings.

        The requested console base port is stored in both:

        * ``self.vm["android"]["android-console-base-port"]`` for minimega launch.
        * ``self.vm["adb"]["android_console_port"]`` as a pre-launch hint for
          the FIREWHEEL ADB handler config.

        minimega's actual post-launch ``android_serial``,
        ``android_console_port``, and ``android_adb_port`` are authoritative
        and are used by the launch plugin before starting the VM Resource Handler.
        """
        current_mem = self.vm.get("mem")
        new_mem = 4096
        if current_mem is None or current_mem < new_mem:
            self.vm["mem"] = new_mem

        vcpu = self.vm.get("vcpu", {})

        # if number of VCPUs is less than min_vcpus, set it
        min_vcpus = 8
        num_vcpus = (
            vcpu.get("sockets", 1) * vcpu.get("cores", 1) * vcpu.get("threads", 1)
        )
        if num_vcpus < min_vcpus:
            if self.vm.get("vcpu") is None:
                self.vm["vcpu"] = {"model": "qemu64"}
            self.vm["vcpu"]["sockets"] = 2
            self.vm["vcpu"]["cores"] = 2
            self.vm["vcpu"]["threads"] = 2

        # Native minimega Android VM type.
        self.vm["vm_type"] = "android"

        # Keep generic FIREWHEEL minimega config generation satisfied.
        self.vm.setdefault("architecture", "x86_64")

        requested_console_port = self._allocate_requested_console_port()

        # Native minimega Android launch configuration. These keys intentionally
        # match minimega's generated ``vm config android-*`` names.
        android_config = self.vm.setdefault("android", {})
        self._configure_android_sdk_paths(android_config)
        android_config.setdefault("android-console-base-port", requested_console_port)
        android_config.setdefault("android-no-window", True)
        android_config.setdefault("android-writable-system", False)

        # Allow multiple emulator instances to share the same AVD definition.
        # Runtime changes, such as APK installs, should still work, but should be
        # treated as ephemeral and not persisted back to the shared AVD.
        extra_args = android_config.setdefault("android-extra-args", ["-no-metrics"])
        if "-read-only" not in extra_args:
            extra_args.append("-read-only")

        snapshot_flags = [
            "-no-snapshot",
            "-no-snapshot-load",
            "-no-snapshot-save",
        ]

        for flag in snapshot_flags:
            if flag not in extra_args:
                extra_args.append(flag)

        networking_flags = [
            # Turn off the wlan0 interface. Note that the `-` means "disable VirtioWifi", it's not it's own arg
            "-feature",
            "-VirtioWifi",
            # Disallows traffic on eth0 (interface still shows up, it just doesn't work)
            "-network-user-mode-options",
            "restrict=on",
        ]

        for flag in networking_flags:
            if flag not in extra_args:
                extra_args.append(flag)

        # FIREWHEEL VM Resource Handler ADB configuration. These are pre-launch
        # hints only. The parse-experiment-graph plugin updates the handler
        # process config with actual minimega post-launch values before starting
        # the ADB driver.
        adb_config = self.vm.setdefault("adb", {})
        adb_config.setdefault("android_console_port", requested_console_port)
        adb_config.setdefault("require_root", True)

    def disable_read_only_avd(self):
        """
        Disable the default Android emulator -read-only flag.

        This should only be used when a topology needs persistent writes to a
        unique per-VM AVD directory.
        """
        self.vm["android_read_only"] = False
        android_config = self.vm.setdefault("android", {})
        extra_args = android_config.get("android-extra-args", [])
        android_config["android-extra-args"] = [
            arg for arg in extra_args if arg != "-read-only"
        ]

    def _preconfigure_networking(self):
        """
        Does some preconfiguration of the Android phone's networking to ensure
        it's compatible with FIREWHEEL. It turns off the eth0 interface which
        is used for the phone to access the internet, which is not desired in
        FIREWHEEL experiments. It also deletes the pre-defined rules in ``ip
        rules`` so that network routing works more like a regular Linux device,
        allowing FIREWHEEL networking options to work correctly.

        Note:
            The Android ADB driver and generated launch scripts use
            ``/system/bin/sh``. Scripts used here should be POSIX ``sh``
            compatible and should not require Bash unless
            ``android_install_bash`` has explicitly been enabled.
        """
        # Disable the eth0 interface, it gives the VM internet access which we don't want
        network_cmd = (
            "ip link set dev eth0 down 2>/dev/null || true; "
            'dev="$(basename "$(readlink -f /sys/class/net/eth0/device)" 2>/dev/null)" || true; '
            '[ -n "$dev" ] && [ -e /sys/bus/virtio/drivers/virtio_net/unbind ] '
            '&& echo "$dev" > /sys/bus/virtio/drivers/virtio_net/unbind || true'
        )

        full_args = f"-c {shlex.quote(network_cmd)}"
        self.run_executable(-20000, "/system/bin/sh", full_args, vm_resource=False)

        # delete android-default routing rules that mess with networking
        self.run_executable(-19999, "fix_routing_rules.sh", vm_resource=True)

    def _replace_text_in_file(self, path, old, new):
        """
        Replace text in a single UTF-8-compatible text file.

        Binary files are skipped automatically.

        Args:
            path (str | pathlib.Path): File to update.
            old (str): Text to replace.
            new (str): Replacement text.

        Returns:
            bool: True if the file was updated, otherwise False.
        """
        path = Path(path)

        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return False
        except OSError:
            return False

        updated = original.replace(old, new)

        if updated == original:
            return False

        path.write_text(updated, encoding="utf-8")
        return True

    def _adjust_avd_template_paths(self, dot_android_path, avd_template_str):
        """
        Replace template paths in Android AVD text configuration files.

        This intentionally avoids running sed over every file in the AVD directory,
        because AVD directories contain large binary image files.

        Args:
            dot_android_path (str | pathlib.Path): Root Android metadata directory.
            avd_template_str (str): Template string to replace in text files.

        Returns:
            list[str]: Paths of text files that were updated.
        """
        dot_android_path = Path(dot_android_path)
        replacement = str(Path(self.current_file_dir).resolve())

        # Known AVD/Android metadata/config files that are text.
        allowed_suffixes = {
            ".ini",
            ".conf",
            ".txt",
            ".cfg",
            ".properties",
        }

        changed_files = []

        for path in dot_android_path.rglob("*"):
            if not path.is_file():
                continue

            if path.suffix not in allowed_suffixes:
                continue

            if self._replace_text_in_file(path, avd_template_str, replacement):
                changed_files.append(str(path))

        return changed_files

    def _read_key_value_file(self, path):
        """
        Read a simple key=value file while preserving original lines.

        Android AVD config.ini files are not INI files in the Python configparser
        sense because they do not have sections.

        Args:
            path (str | pathlib.Path): File to read.

        Returns:
            tuple[list[str], dict[str, str]]: Original file lines and parsed
                key/value mappings.
        """
        path = Path(path)
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

        values = {}

        for line in lines:
            stripped = line.strip()

            if not stripped or stripped.startswith("#") or stripped.startswith(";"):
                continue

            if "=" not in stripped:
                continue

            key, value = stripped.split("=", 1)
            values[key.strip()] = value.strip()

        return lines, values

    def _write_key_value_updates(self, path, updates=None, remove_keys=None):
        """
        Apply key=value updates to a simple key=value file.

        Args:
            path (str | pathlib.Path): File to update.
            updates (dict): Key/value pairs to set.
            remove_keys (set): Keys to remove.

        Returns:
            bool: True if the file changed.
        """
        path = Path(path)
        updates = dict(updates or {})
        remove_keys = set(remove_keys or set())

        lines, _values = self._read_key_value_file(path)

        new_lines = []
        changed = False
        remaining_updates = dict(updates)

        for line in lines:
            stripped = line.strip()

            if (
                stripped
                and not stripped.startswith("#")
                and not stripped.startswith(";")
                and "=" in stripped
            ):
                key, _value = stripped.split("=", 1)
                key = key.strip()

                if key in remove_keys:
                    changed = True
                    continue

                if key in remaining_updates:
                    new_line = f"{key}={remaining_updates.pop(key)}\n"

                    if line != new_line:
                        changed = True

                    new_lines.append(new_line)
                    continue

            new_lines.append(line)

        for key, value in remaining_updates.items():
            new_lines.append(f"{key}={value}\n")
            changed = True

        if changed:
            path.write_text("".join(new_lines), encoding="utf-8")

        return changed

    def cleanup_avd_skin_config(
        self,
        avd,
        fallback_skin_name=None,
        remove_skin_path=True,
        disable_device_frame=True,
        only_if_skin_path_missing=False,
    ):
        """
        Make an AVD independent of unavailable named emulator skins.

        Some AVDs created by Android Studio reference a device skin such as
        ``pixel_9a`` using:

            skin.name=pixel_9a
            skin.path=/path/to/Android/Sdk/skins/pixel_9a

        If that skin directory is not present, the emulator can fail with:

            ERROR | unknown skin name 'pixel_9a'

        FIREWHEEL does not need the visual device frame, so this method converts the
        AVD to a generic resolution-based skin.

        Args:
            avd (str): AVD name, e.g. ``"Pixel_9a"``.
            fallback_skin_name (str | None): Resolution skin name. If None, derive
                from ``hw.lcd.width`` and ``hw.lcd.height``.
            remove_skin_path (bool): Remove ``skin.path`` from config.ini.
            disable_device_frame (bool): Set ``showDeviceFrame=no``.
            only_if_skin_path_missing (bool): If True, only modify the config when
                ``skin.path`` is set but does not exist.

        Returns:
            bool: True if the config changed, False otherwise.
        """
        avd_name = str(avd)

        if avd_name.endswith(".avd"):
            avd_dir_name = avd_name
        else:
            avd_dir_name = f"{avd_name}.avd"

        config_path = (
            Path(self.current_file_dir)
            / ".android"
            / "avd"
            / avd_dir_name
            / "config.ini"
        )

        if not config_path.exists():
            return False

        _lines, values = self._read_key_value_file(config_path)

        skin_path = values.get("skin.path")

        if only_if_skin_path_missing and skin_path:
            expanded_skin_path = Path(skin_path).expanduser()

            if expanded_skin_path.exists():
                return False

        if fallback_skin_name is None:
            width = values.get("hw.lcd.width")
            height = values.get("hw.lcd.height")

            if width and height:
                fallback_skin_name = f"{width}x{height}"
            else:
                # Safe generic fallback for the current Pixel_9a AVD.
                fallback_skin_name = "1080x2424"

        updates = {
            "skin.name": fallback_skin_name,
            "skin.dynamic": "yes",
        }

        if disable_device_frame:
            updates["showDeviceFrame"] = "no"

        remove_keys = set()

        if remove_skin_path:
            remove_keys.add("skin.path")

        return self._write_key_value_updates(
            config_path,
            updates=updates,
            remove_keys=remove_keys,
        )

    def set_avd(
        self,
        avd,
        avd_template_str="REPLACE_WITH_FULL_PATH",
        path_adjustment_needed=True,
        cleanup_skin_config=True,
        fallback_skin_name=None,
    ):
        """
        Set the name of the Android Virtual Device (AVD) to be launched.

        Args:
            avd (str): The name of the AVD.
            avd_template_str (str): A hard-coded value that represents the base
                path to the AVD. This is the value that will be replaced with the
                full path to the .android/avd directory within this model
                component. Defaults to "REPLACE_WITH_FULL_PATH".
            path_adjustment_needed (bool): Whether the path adjustment needs to
                occur. For example, if multiple phones using the same AVD are in
                the same network, the path replacement does not need to happen
                twice.
            cleanup_skin_config (bool): Whether to make the AVD independent of an
                unavailable named emulator skin.
            fallback_skin_name (str | None): Optional resolution-based skin name.
                If None, this is derived from hw.lcd.width and hw.lcd.height in
                config.ini.

        Note:
            This method configures native minimega Android launch fields under
            ``self.vm["android"]`` rather than old wrapper-style ``qemu_append``
            fields.
        """
        self.vm["image"] = avd

        android_config = self.vm.setdefault("android", {})
        android_config["android-avd"] = avd
        android_config["android-avd-dir"] = os.path.join(
            self.current_file_dir,
            ".android",
            "avd",
        )

        dot_android_path = os.path.join(self.current_file_dir, ".android")

        if path_adjustment_needed:
            self._adjust_avd_template_paths(
                dot_android_path=dot_android_path,
                avd_template_str=avd_template_str,
            )

        self._validate_avd_ini(avd)

        if cleanup_skin_config:
            self.cleanup_avd_skin_config(
                avd=avd,
                fallback_skin_name=fallback_skin_name,
                remove_skin_path=True,
                disable_device_frame=True,
                only_if_skin_path_missing=False,
            )

    def install_bash(self):
        """
        Optionally install Bash inside the phone for legacy or Bash-specific resources.

        This is not required by the FIREWHEEL ADB driver and is not enabled by
        default. The ADB driver uses ``/system/bin/sh`` for generated launch
        scripts.

        When used this method schedules the library and Bash
        installation resources and requests writable-system behavior from minimega.

        Note:
            This intentionally installs Bash as ``/system/bin/bash`` rather than
            relying on ``/bin/bash``. Android systems commonly provide
            ``/system/bin/sh`` and may not provide ``/bin``.
        """
        self.vm.setdefault("android", {})["android-writable-system"] = True
        self.disable_read_only_avd()
        self.drop_file(
            -10001,
            "/system/lib64/libandroid-support.so",
            "libandroid-support.so",
        )
        self.drop_file(
            -10001,
            "/system/lib64/libreadline.so.8",
            "libreadline.so.8.3",
        )
        self.drop_file(
            -10001,
            "/system/lib64/libiconv.so",
            "libiconv.so",
        )
        self.drop_file(
            -10001,
            "/system/lib64/libncursesw.so.6",
            "libncursesw.so.6.5",
        )

        android_bash_fn = "bash-android-v5.3.9-x86_64"
        self.drop_file(
            -10000,
            "/data/local/tmp/bash",
            android_bash_fn,
            executable=True,
        )
        self.run_executable(
            -9999,
            "/system/bin/mv",
            ["-f", "/data/local/tmp/bash", "/system/bin/bash"],
            vm_resource=False,
        )

    def set_hostname(self, start_time=-250):
        """
        Wrapper to run the vm_resource that sets the hostname of the VM.

        Args:
            start_time (int, optional): The start time to configure the VM's
                hostname (default=-250).
        """
        self.run_executable(
            start_time,
            "set_hostname_android.sh",
            self.name,
            vm_resource=True,
        )

    def install_apk(self, start_time, filenames, split=False):
        """
        Install Android APK file(s) on the phone.

        Args:
            start_time (int): The time at which installation should start.
            filenames (str | list[str] | tuple[str]): APK filename or APK filenames.
            split (bool): If True, treat ``filenames`` as one split APK package and
                install them together. If False, treat ``filenames`` as independent
                APKs and install each separately.

        Raises:
            ValueError: If no APK filenames are provided.

        Note:
            The installer helper and APK files are staged into the same schedule
            working directory. The helper waits for Android's Package Manager before
            installing.
        """
        if isinstance(filenames, str):
            apk_filenames = [filenames]
        else:
            apk_filenames = list(filenames)

        if not apk_filenames:
            raise ValueError("At least one APK filename must be provided.")

        apk_basenames = [os.path.basename(filename) for filename in apk_filenames]

        mode = "--split" if split else "--independent"

        entry = self.run_executable(
            start_time,
            "install_apk_android.sh",
            [mode, *apk_basenames],
            vm_resource=True,
        )

        for source_filename, apk_basename in zip(apk_filenames, apk_basenames):
            entry.add_file(apk_basename, source_filename)

    def add_root_profiles(self):
        """
        Android does not use the Linux root profile setup.

        The LinuxHost implementation drops SSH keys, shell profiles, vimrc files,
        and related content under ``/root``. Android devices do not generally use
        ``/root`` as an interactive user home, and the FIREWHEEL ADB driver does not
        require SSH, Bash, or Linux-style root profiles.

        This method intentionally overrides ``LinuxHost.add_root_profiles()`` with
        a no-op for Android.
        """
        self.log.debug(
            "Skipping Linux root profile setup for Android phone %s.", self.name
        )

    def configure_ips(self, start_time=-200):
        """
        Configure the IP addresses of the VM

        Args:
            start_time (int): The start time to configure the VM's hostname (default=-200)

        Returns:
            bool: True if successful, False otherwise.
        """
        config = self._configure_ips()

        if not config:
            return

        self.add_vm_resource(start_time, "configure_ips_android.sh", config)

        return True
