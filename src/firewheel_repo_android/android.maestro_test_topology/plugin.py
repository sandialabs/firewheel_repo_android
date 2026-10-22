from android.maestro import AndroidMaestroEndpoint
from android.pixel9a import AndroidPixel9a

from firewheel.control.experiment_graph import Vertex, AbstractPlugin


class AndroidMaestroTestTopology(AbstractPlugin):
    """
    A simple test topology for android.maestro.

    This topology launches one Android Pixel 9a phone and schedules one or more
    host-side Maestro flows against it.

    Example usage:

        firewheel experiment android.maestro_test_topology:test_case=settings_check minimega.launch -r

        firewheel experiment android.maestro_test_topology:test_case=settings_network minimega.launch -r

        firewheel experiment android.maestro_test_topology:test_case=settings_search minimega.launch -r

        firewheel experiment android.maestro_test_topology:test_case=expected_failure minimega.launch -r

        firewheel experiment android.maestro_test_topology:test_case=all minimega.launch -r
    """

    VALID_TEST_CASES = {
        "settings_check",
        "settings_network",
        "settings_search",
        "expected_failure",
        "all",
    }

    FLOW_RESOURCES = {
        "settings_check": "settings_check.yaml",
        "settings_network": "settings_network.yaml",
        "settings_search": "settings_search.yaml",
        "expected_failure": "expected_failure.yaml",
    }

    def run(
        self,
        test_case="settings_check",
        start_time="10",
        timeout="120",
        fail_experiment_on_failure="false",
    ):
        """
        Create a one-phone Android Maestro test topology.

        Args:
            test_case (str): Which Maestro test case to run. Supported values:

                ``settings_check``:
                    Launch Settings and assert basic expected UI state.

                ``settings_network``:
                    Navigate from Settings into Network/Internet settings.

                ``settings_search``:
                    Exercise Settings search and text input.

                ``expected_failure``:
                    Run a flow that is expected to fail. Useful for validating
                    Maestro artifact and failure collection. By default this does
                    not fail the FIREWHEEL experiment unless
                    ``fail_experiment_on_failure=true`` is passed.

                ``all``:
                    Run settings_check, settings_network, and settings_search.
                    Does not include expected_failure.

            start_time (str): Schedule time for the first Maestro flow.
            timeout (str): Timeout for each Maestro flow in seconds.
            fail_experiment_on_failure (str): If true, a Maestro failure causes
                the host-based runner to exit nonzero.

        Raises:
            RuntimeError: If an unknown test case is requested.
            ValueError: If start_time or timeout cannot be converted to integers.
        """
        test_case = str(test_case).strip().lower()
        start_time = int(start_time)
        timeout = int(timeout)
        fail_experiment_on_failure = self._to_bool(fail_experiment_on_failure)

        if test_case not in self.VALID_TEST_CASES:
            raise RuntimeError(
                f"Unknown Maestro test_case={test_case!r}. "
                f"Valid cases are: {sorted(self.VALID_TEST_CASES)}"
            )

        phone = Vertex(self.g, "android-0")
        phone.decorate(AndroidPixel9a)
        phone.decorate(AndroidMaestroEndpoint)

        if test_case == "all":
            flow_names = [
                "settings_check",
                "settings_network",
                "settings_search",
            ]
        else:
            flow_names = [test_case]

        for index, flow_name in enumerate(flow_names):
            phone.add_maestro_flow(
                start_time=start_time + index * 10,
                flow_resource=self.FLOW_RESOURCES[flow_name],
                timeout=timeout,
                fail_experiment_on_failure=fail_experiment_on_failure,
            )

    @staticmethod
    def _to_bool(value):
        """
        Convert common string values to bool.

        Args:
            value (bool | str): Value to convert.

        Returns:
            bool: Converted boolean value.

        Raises:
            ValueError: If ``value`` is not a recognized boolean string.
        """
        if isinstance(value, bool):
            return value

        value = str(value).strip().lower()

        if value in {"1", "true", "yes", "y", "on"}:
            return True

        if value in {"0", "false", "no", "n", "off"}:
            return False

        raise ValueError(f"Invalid boolean value: {value!r}")
