from base_objects import Switch
from android.pixel9a import AndroidPixel9a

from firewheel.control.experiment_graph import Vertex, AbstractPlugin


class AndroidTestTopology(AbstractPlugin):
    """A parameterized test topology for Android phones."""

    VALID_TEST_CASES = {
        "smoke",
        "same_avd",
        "apk",
        "network",
        "network_apk",
        "no_read_only_negative",
        "all",
    }

    def run(
        self,
        size="1",
        test_case="smoke",
        apk="wikipedia.apk",
        start_apk="-50",
        start_ping="1",
    ):
        """
        Create Android Pixel9a test topologies.

        Args:
            size (str): Number of Android phones to launch.
            test_case (str): Which test case to run. Supported values:

                ``smoke``:
                    Launch one or more Android phones without additional test resources.

                ``same_avd``:
                    Launch multiple Android phones from the same AVD using the default
                    ``-read-only`` behavior. Use ``size > 1`` to validate shared-AVD behavior.

                ``apk``:
                    Launch Android phones and install an APK. Defaults to ``wikipedia.apk``.
                    This validates APK installation while the AVD is in read-only mode.

                ``network``:
                    Connect all Android phones to a switch and schedule an Android-native
                    ping test.

                ``network_apk``:
                    Run both the network and APK-install tests.

                ``all``:
                    Alias for ``network_apk``.

                ``no_read_only_negative``:
                    Disable the default ``-read-only`` flag. For ``size > 1`` and a shared
                    AVD, this is expected to fail and is useful as a negative test.

            apk (str): APK filename to install for APK test cases. Defaults to
                ``wikipedia.apk``.
            start_apk (str): Schedule time for APK install.
            start_ping (str): Schedule time for network ping test.

        Raises:
            RuntimeError: If an unknown test case is requested.
            ValueError: If ``size``, ``start_apk``, or ``start_ping`` cannot be
                converted to integers.
        """
        size = int(size)
        if size < 1:
            raise ValueError("size must be at least 1.")

        start_apk = int(start_apk)
        start_ping = int(start_ping)

        test_case = str(test_case).strip().lower()

        if test_case not in self.VALID_TEST_CASES:
            raise RuntimeError(
                f"Unknown Android test_case={test_case!r}. "
                f"Valid cases are: {sorted(self.VALID_TEST_CASES)}"
            )

        if test_case == "no_read_only_negative" and size < 2:
            raise ValueError("no_read_only_negative requires size >= 2.")

        phones = []
        for i in range(size):
            phone = Vertex(self.g, f"android-{i}")
            phone.decorate(AndroidPixel9a)

            if test_case == "no_read_only_negative":
                phone.disable_read_only_avd()

            phones.append(phone)

        if test_case in {"network", "network_apk", "all"}:
            self._connect_phones_to_switch(phones)
            self._schedule_ping_test(phones, start_time=start_ping)

        if test_case in {"apk", "network_apk", "all"}:
            self._schedule_apk_install(phones, apk=apk, start_time=start_apk)

    def _connect_phones_to_switch(self, phones):
        """
        Connect all Android phones to a single switch.

        Args:
            phones (list): Android phone vertices.
        """
        switch = Vertex(self.g, "android-switch")
        switch.decorate(Switch)

        for i, phone in enumerate(phones):
            phone.connect(
                switch,
                f"1.0.0.{i + 1}",
                "255.0.0.0",
            )

    def _schedule_ping_test(self, phones, start_time=-1):
        """
        Schedule an Android-native ping test on each phone.

        Args:
            phones (list): Android phone vertices.
            start_time (int): Schedule time for the ping test.
        """
        targets = [f"1.0.0.{i + 1}" for i in range(len(phones))]
        arguments = " ".join(targets)

        for phone in phones:
            phone.run_executable(
                start_time,
                "ping_all_android.sh",
                arguments,
                vm_resource=True,
            )

    def _schedule_apk_install(self, phones, apk="wikipedia.apk", start_time=-50):
        """
        Schedule APK installation on each phone.

        Args:
            phones (list): Android phone vertices.
            apk (str): APK filename.
            start_time (int): Schedule time for APK install.
        """
        apk_files = [item.strip() for item in apk.split(",") if item.strip()]
        for phone in phones:
            phone.install_apk(start_time, apk_files)
