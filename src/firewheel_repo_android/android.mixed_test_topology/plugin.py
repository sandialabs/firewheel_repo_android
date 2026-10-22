from netaddr import IPNetwork
from base_objects import Switch
from android.pixel9a import AndroidPixel9a
from linux.ubuntu2204 import Ubuntu2204Server

from firewheel.control.experiment_graph import Vertex, AbstractPlugin


def allocate_hosts(network_cidr, count, label):
    """
    Allocate host IPs from a CIDR block.

    Args:
        network_cidr (str): CIDR block to allocate from.
        count (int): Number of host IPs needed.
        label (str): Human-readable name for error messages.

    Returns:
        list[str]: Allocated host IP addresses.

    Raises:
        ValueError: If the CIDR block does not contain enough usable host
            addresses.
    """
    hosts = []

    for ip_addr in IPNetwork(network_cidr).iter_hosts():
        hosts.append(str(ip_addr))

        if len(hosts) == count:
            return hosts

    raise ValueError(
        f"Requested {count} {label} IP addresses, but {network_cidr} "
        "does not contain enough usable host addresses."
    )


class AndroidUbuntuMixedTopology(AbstractPlugin):
    """
    A mixed Android + Ubuntu topology for validating Android/ADB support
    alongside conventional Linux/QGA VMs.
    """

    def run(
        self,
        android_count="1",
        ubuntu_count="1",
        start_ping="1",
    ):
        """
        Create a mixed Android + Ubuntu topology.

        Args:
            android_count (str): Number of Android Pixel 9a phones to create.
            ubuntu_count (str): Number of Ubuntu2204Server VMs to create.
            start_ping (str): Schedule time for ping tests.

        Raises:
            ValueError: If VM counts or start time cannot be converted to integers,
                or if either VM count is less than 1.
        """
        android_count = int(android_count)
        ubuntu_count = int(ubuntu_count)
        start_ping = int(start_ping)

        if android_count < 1:
            raise ValueError("android_count must be at least 1.")

        if ubuntu_count < 1:
            raise ValueError("ubuntu_count must be at least 1.")

        switch = Vertex(self.g, "mixed-switch")
        switch.decorate(Switch)

        # Allocate from separate /24 pools for readability while assigning all
        # VM interfaces a broad /8 netmask so they are directly reachable on
        # the same shared switch without a router.
        android_network = IPNetwork("10.0.0.0/24")
        ubuntu_network = IPNetwork("10.0.1.0/24")
        experiment_network = IPNetwork("10.0.0.0/8")
        vm_netmask = str(experiment_network.netmask)

        android_ips = allocate_hosts(
            str(android_network),
            android_count,
            "Android",
        )
        ubuntu_ips = allocate_hosts(
            str(ubuntu_network),
            ubuntu_count,
            "Ubuntu",
        )

        androids = []
        servers = []

        for idx, android_ip in enumerate(android_ips):
            phone = Vertex(self.g, f"android-{idx}")
            phone.decorate(AndroidPixel9a)
            phone.connect(
                switch,
                android_ip,
                vm_netmask,
            )
            androids.append(phone)

        for idx, ubuntu_ip in enumerate(ubuntu_ips):
            server = Vertex(self.g, f"server-{idx}")
            server.decorate(Ubuntu2204Server)
            server.connect(
                switch,
                ubuntu_ip,
                vm_netmask,
            )
            servers.append(server)

        # Android phones ping Ubuntu servers.
        for phone in androids:
            for offset, ubuntu_ip in enumerate(ubuntu_ips):
                phone.run_executable(
                    start_ping + offset,
                    "/system/bin/ping",
                    ["-c", "2", ubuntu_ip],
                    vm_resource=False,
                )

        # Ubuntu servers ping Android phones.
        for server in servers:
            for offset, android_ip in enumerate(android_ips):
                server.run_executable(
                    start_ping + offset,
                    "ping",
                    ["-c", "2", android_ip],
                    vm_resource=False,
                )
