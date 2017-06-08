# Collectd plugin for Cumulus Quagga/FRR

This plugin will collect BGP neighbor-related metrics from Quagga for
a given family. It's quite rudimentary.

It requires a version of Quagga able to understand the `show bgp <afi>
<safi> summary json` commands (Quagga from Cumulus, FRR).

## Installation

The plugin should be copied in `/usr/share/collectd/python/` or
another place specified by `ModulePath` in the Python plugin
configuration. The `types.quagga.db` file also needs to be copied in
`/usr/share/collectd/` and registered with `TypesDB`.

## Configuration

This should be used like this:

    LoadPlugin python
    TypesDB "/usr/share/collectd/types.quagga.db"

    <Plugin python>
      ModulePath "/usr/share/collectd/python"
      Import "quagga"
      <Module quagga>
        socket "/var/run/quagga/bgpd.vty"
        family "evpn"
      </Module>
    </Plugin>

Only the configuration keys exposed in the example are valid. Their
default values are the ones in the example.

# Testing

A one-time collection can be triggered with:

    collectd -C collectd.conf -T
