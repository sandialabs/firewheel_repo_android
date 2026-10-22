"""This module contains all necessary Model Component Objects for android.pixel9a."""

import os
import shutil
import fnmatch

from android.base_objects import AndroidPhone

from firewheel.control.experiment_graph import require_class


@require_class(AndroidPhone)
class AndroidPixel9a:
    """
    The class representing an Android Pixel9a phone.
    """

    # Static variable to determine whether the AVD is already installed for
    # this experiment.
    AVD_INSTALLED = False

    def __init__(self):
        """
        Initialize the object as a Pixel9a phone.
        """
        self._verify_pixel9a_setup()
        self.install_avd()

    def _verify_pixel9a_setup(self):
        """
        Ensures that the user has extracted Pixel_9a.avd.tgz before running.

        Raises:
            RuntimeError: If the tarball has not been extracted.
        """
        err_msg = "Make sure to extract Pixel_9a.avd.tgz before running"

        current_file_dir = os.path.dirname(__file__)
        if not os.path.exists(os.path.join(current_file_dir, "Pixel_9a.avd")):
            raise RuntimeError(err_msg)

    def _ignore_avd_runtime_state(self, _directory, names):
        """
        Ignore Android emulator runtime/snapshot state while staging the AVD.

        These files are not part of the reusable AVD definition and may have
        restrictive permissions if created by a previous emulator run. Copying
        them into android_base/.android/avd can break later cleanup.

        Args:
            _directory (str): Directory currently being copied. Unused.
            names (list[str]): Names in the current directory.

        Returns:
            list[str]: Names to ignore.
        """
        ignored_patterns = {
            "snapshots",
            "pstore",
            "default_boot",
            "*.lock",
            "*.lck",
        }

        ignored = []

        for name in names:
            if any(fnmatch.fnmatch(name, pattern) for pattern in ignored_patterns):
                ignored.append(name)

        return ignored

    def install_avd(self):
        """
        Copies the AVD file into the android_base .android/avd directory,
        making it available to the emulator. This also sets the AVD as
        Pixel_9a.
        """
        if AndroidPixel9a.AVD_INSTALLED:
            self.set_avd("Pixel_9a", path_adjustment_needed=False)
            return

        current_file_dir = os.path.dirname(__file__)
        dst_dir = os.path.join(current_file_dir, "../android_base/.android/avd")

        avd_name = "Pixel_9a.avd"
        src_path = os.path.join(current_file_dir, avd_name)
        dst_path = os.path.join(dst_dir, avd_name)

        shutil.copytree(
            src_path,
            dst_path,
            dirs_exist_ok=True,
            ignore=self._ignore_avd_runtime_state,
        )

        ini_name = "Pixel_9a.ini"
        src_path = os.path.join(current_file_dir, ini_name)
        dst_path = os.path.join(dst_dir, ini_name)
        shutil.copy2(src_path, dst_path)

        self.set_avd("Pixel_9a")

        AndroidPixel9a.AVD_INSTALLED = True
