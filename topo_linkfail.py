"""
topolinkfail.py
---------------
Mininet Triangle Topology for Link Failure Detection & Recovery Project.

Topology:
    h1 --- s1 --- s2 --- h2
            \     /
              s3

Usage:
    sudo mn --controller=remote,ip=127.0.0.1,port=6633 \
            --custom topo_linkfail.py --topo mytopo \
            --switch ovsk --mac
"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink


class TriangleTopo(Topo):
    """
    Triangle topology with 3 switches and 2 hosts.

    h1 -- s1 -- s2 -- h2
           \   /
            s3

    Links:
        h1  <-> s1  (host link)
        h2  <-> s2  (host link)
        s1  <-> s2  (primary path)
        s1  <-> s3  (alternate path leg 1)
        s2  <-> s3  (alternate path leg 2)
    """

    def build(self):
        # Add hosts
        h1 = self.addHost('h1', mac='00:00:00:00:00:01', ip='10.0.0.1/24')
        h2 = self.addHost('h2', mac='00:00:00:00:00:02', ip='10.0.0.2/24')

        # Add switches
        s1 = self.addSwitch('s1', protocols='OpenFlow13')
        s2 = self.addSwitch('s2', protocols='OpenFlow13')
        s3 = self.addSwitch('s3', protocols='OpenFlow13')

        # Host-to-switch links (no bandwidth limit)
        self.addLink(h1, s1)
        self.addLink(h2, s2)

        # Switch-to-switch links with bandwidth and delay for realistic simulation
        # bw=100 Mbps, delay=1ms
        self.addLink(s1, s2, bw=100, delay='1ms', loss=0)   # primary path
        self.addLink(s1, s3, bw=100, delay='1ms', loss=0)   # alternate leg 1
        self.addLink(s2, s3, bw=100, delay='1ms', loss=0)   # alternate leg 2


# Register topology so Mininet can discover it via --topo mytopo
topos = {'mytopo': TriangleTopo}


def run():
    """
    Standalone runner — use when NOT passing --custom to mn CLI.
    Starts the network and drops into Mininet CLI.
    """
    setLogLevel('info')
    topo = TriangleTopo()
    net = Mininet(
        topo=topo,
        controller=lambda name: RemoteController(
            name, ip='127.0.0.1', port=6633
        ),
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        waitConnected=True,
    )

    net.start()
    info('\n*** Topology started — dropping into CLI\n')
    info('*** To simulate link failure:  link s1 s2 down\n')
    info('*** To restore link:           link s1 s2 up\n')
    info('*** To dump flows:             sh ovs-ofctl dump-flows s1\n\n')
    CLI(net)
    net.stop()


if __name__ == '__main__':
    run()