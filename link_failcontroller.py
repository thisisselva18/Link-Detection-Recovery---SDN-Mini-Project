"""
link_failcontroller.py
---------------------
Ryu SDN Controller: Link Failure Detection & Recovery
------------------------------------------------------
Features:
  - OpenFlow 1.3
  - Topology discovery (EventSwitchEnter, EventLinkAdd, EventLinkDelete)
  - Shortest-path routing via NetworkX (Dijkstra)
  - Automatic flow rule installation on all switches
  - Dynamic rerouting on link failure / link restoration
  - MAC learning fallback via packet_in

Usage:
    ryu-manager link_failcontroller.py --observe-links
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (
    CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER, set_ev_cls
)
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types
from ryu.topology import event as topo_event

import networkx as nx
import logging

LOG = logging.getLogger('LinkFailController')
LOG.setLevel(logging.DEBUG)


class LinkFailController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(LinkFailController, self).__init__(*args, **kwargs)

        self.net = nx.DiGraph()
        self.mac_to_port = {}
        self.datapaths = {}
        self.port_map = {}
        self.host_location = {}

    def _add_flow(self, datapath, priority, match, actions):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        inst = [parser.OFPInstructionActions(
            ofproto.OFPIT_APPLY_ACTIONS, actions)]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst
        )
        datapath.send_msg(mod)

    def _install_table_miss(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(
            ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(datapath, 0, match, actions)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        self.datapaths[dp.id] = dp
        self._install_table_miss(dp)

    @set_ev_cls(topo_event.EventSwitchEnter)
    def switch_enter_handler(self, ev):
        dpid = ev.switch.dp.id
        self.net.add_node(dpid)

    @set_ev_cls(topo_event.EventLinkAdd)
    def link_add_handler(self, ev):
        src = ev.link.src
        dst = ev.link.dst

        self.net.add_edge(src.dpid, dst.dpid)
        self.port_map[(src.dpid, dst.dpid)] = src.port_no

        LOG.info("Link UP: %s -> %s", hex(src.dpid), hex(dst.dpid))

    @set_ev_cls(topo_event.EventLinkDelete)
    def link_delete_handler(self, ev):
        src = ev.link.src
        dst = ev.link.dst

        LOG.warning("🔥 LINK DOWN: %s -> %s", hex(src.dpid), hex(dst.dpid))

        if self.net.has_edge(src.dpid, dst.dpid):
            self.net.remove_edge(src.dpid, dst.dpid)

        if self.net.has_edge(dst.dpid, src.dpid):
            self.net.remove_edge(dst.dpid, src.dpid)

        self._reinstall_paths()

    def _reinstall_paths(self):
        for src in self.host_location:
            for dst in self.host_location:
                if src != dst:
                    self._install_path(src, dst)

    def _install_path(self, src_mac, dst_mac):
        if src_mac not in self.host_location or dst_mac not in self.host_location:
            return

        src_dpid, _ = self.host_location[src_mac]
        dst_dpid, dst_port = self.host_location[dst_mac]

        try:
            path = nx.shortest_path(self.net, src_dpid, dst_dpid)
        except:
            return
            
            if not path or len(path) < 1:
                return

        LOG.info("Path %s -> %s: %s",
                 src_mac, dst_mac, " -> ".join(hex(x) for x in path))

        for i, dpid in enumerate(path):
            dp = self.datapaths.get(dpid)
            if not dp:
                continue

            parser = dp.ofproto_parser

            if dpid == dst_dpid:
                out_port = dst_port
            else:
                next_dpid = path[i + 1]
                out_port = self.port_map.get((dpid, next_dpid))
                if not out_port:
                    return

            match = parser.OFPMatch(eth_src=src_mac, eth_dst=dst_mac)
            actions = [parser.OFPActionOutput(out_port)]
            
            LOG.info("Installing flow on %s: %s -> %s via port %s", hex(dpid), src_mac, dst_mac, out_port)

            self._add_flow(dp, 10, match, actions)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        dpid = dp.id
        parser = dp.ofproto_parser
        ofproto = dp.ofproto

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if not eth or eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        src = eth.src
        dst = eth.dst
        
        if eth.ethertype not in (ether_types.ETH_TYPE_IP, ether_types.ETH_TYPE_ARP):
            return
        
        if dst.startswith("33:33"):
            return
      
        in_port = msg.match['in_port']

        # Learn host location
        if src not in self.host_location:
            self.host_location[src] = (dpid, in_port)
            LOG.info("Host learned: %s at %s", src, hex(dpid))

    # ❌ If destination unknown → DROP (NO FLOOD)
        if dst not in self.host_location:
            actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]

            data = None
            if msg.buffer_id == ofproto.OFP_NO_BUFFER:
                data = msg.data

            out = parser.OFPPacketOut(
                datapath=dp,
                buffer_id=msg.buffer_id,
                in_port=in_port,
                actions=actions,
                data=data
            )
            dp.send_msg(out)
            return

        src_dpid, _ = self.host_location[src]
        dst_dpid, dst_port = self.host_location[dst]

        try:
            path = nx.shortest_path(self.net, src_dpid, dst_dpid)
        except:
            return

    # Install path ONCE
        self._install_path(src, dst)

    # Forward THIS packet properly
        if dpid == dst_dpid:
            out_port = dst_port
        else:
            next_hop = path[path.index(dpid) + 1]
            out_port = self.port_map[(dpid, next_hop)]

        actions = [parser.OFPActionOutput(out_port)]
        
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
            
        out = parser.OFPPacketOut(
            datapath=dp,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=msg.data
        )
        dp.send_msg(out)