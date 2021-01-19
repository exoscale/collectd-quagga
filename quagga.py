#!/usr/bin/env python

"""Collectd module to extract statistics from a running Quagga daemon."""

from __future__ import print_function
from __future__ import unicode_literals

import json
import socket
import collectd
import sys

class Quagga(object):

    """Extract information from Quagga using VTY socket."""

    def __init__(self, socket):
        self.socket = socket

    def get_bgp_neighbors(self, family):
        """Return BGP neighbor information for the given family.

        Possible values for family are:

          - ipv4 unicast
          - ipv6 unicast
          - evpn
          - ...
        """
        states = {"idle": 1,
                  "connect": 2,
                  "active": 3,
                  "opensent": 4,
                  "openconfirm": 5,
                  "established": 6,
                  "clearing": 7,
                  "deleted": 7}
        data = self._query("show bgp {} summary json".format(family))
        data = json.loads(data)
        results = {}
        for k, v in data['peers'].items():
            collectd.debug("bgp: got {} => {}".format(k, v))
            if v.get('dynamicPeer'):
                continue
            current = {}
            if "state" in v:
                current['state'] = states.get(v["state"].lower(), 0)
            if "hostname" in v:
                current['hostname'] = v['hostname']
            if "peerUptimeMsec" in v:
                current['uptime'] = v['peerUptimeMsec']/1000
            if "prefixReceivedCount" in v:
                current['prefixes'] = v['prefixReceivedCount']
            results[k] = current
        return results

    def _query(self, query):
        collectd.debug("query: connecting to Quagga with "
                       "socket {}".format(self.socket))
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(self.socket)

            # Send the query
            collectd.debug("query: send {}".format(query))
            if sys.version_info > (3, 0):
                sock.sendall(("{}\0".format(query)).encode())
            else:
                sock.sendall("{}\0".format(query))


            data = []
            while True:
                if sys.version_info > (3, 0):
                    more = sock.recv(1024).decode()
                else:
                    more = sock.recv(1024)
                if not more:
                    break
                collectd.debug("query: got {}".format(more.rstrip('\x00')))
                data.append(more.rstrip('\x00'))
                if more.endswith("\0"):
                    break
        finally:
            sock.close()
        return "".join(data)


class QuaggaCollectd(object):

    socket = "/var/run/quagga/bgpd.vty"
    family = "ipv4 unicast"
    usehostname = True

    def configure(self, conf, **kwargs):

        """Collectd configuration callback."""
        if conf is not None:
            kwargs.update({node.key.lower(): node.values
                           for node in conf.children})
        for keyword in kwargs:
            if not isinstance(kwargs[keyword], (list, tuple)):
                kwargs[keyword] = [kwargs[keyword]]
            if keyword == "socket":
                if len(kwargs[keyword]) != 1:
                    raise ValueError("config: socket expects exactly "
                                     "one argument")
                self.socket = kwargs[keyword][0]
            elif keyword == "family":
                if len(kwargs[keyword]) != 1:
                    raise ValueError("config: instance expects exactly "
                                     "one argument")
                self.family = kwargs[keyword][0]
            elif keyword == "usehostname":
                if len(kwargs[keyword]) != 1:
                    raise ValueError("config: usehostname expects exactly "
                                     "one argument")
                if not isinstance(kwargs[keyword][0], bool):
                    raise ValueError("config: usehostname expects a bool")
                self.usehostname = kwargs[keyword][0]
            else:
                raise ValueError("config: unknown keyword "
                                 "`{}`".format(keyword))

    def init(self):
        """Collectd init callback."""
        self.quagga = Quagga(self.socket)

    def dispatch(self, values, instance, type, type_instance):
        """Dispatch a value to collectd."""
        if values is None or any([v is None for v in values]):
            return
        metric = collectd.Values(values=values,
                                 plugin="quagga",
                                 plugin_instance=instance,
                                 type=type,
                                 type_instance=type_instance)
        metric.dispatch()

    def read(self):
        """Collectd read callback."""
        # BGP
        bgp = self.quagga.get_bgp_neighbors(self.family)
        for p in bgp:
            k = p
            if self.usehostname:
                k = bgp[p].get("hostname", k)
            self.dispatch([bgp[p].get("state", 0),
                           bgp[p].get("uptime", 0),
                           bgp[p].get("prefixes", 0)],
                          "bgp_{}".format(self.family).replace(" ", "_"),
                          "quagga_bgp_neighbor", k)


quagga = QuaggaCollectd()
collectd.register_config(quagga.configure)
collectd.register_init(quagga.init)
collectd.register_read(quagga.read)
