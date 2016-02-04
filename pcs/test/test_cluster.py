from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import sys
import shutil
import unittest
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)

import utils
from pcs_test_functions import pcs, ac, isMinimumPacemakerVersion
from pcs_test_functions import PcsRunner
from pcs_test_assertions import AssertPcsMixin
import cluster
from cluster import NodeActionTask


empty_cib = "empty-withnodes.xml"
temp_cib = "temp.xml"

class ClusterTest(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)
        if os.path.exists("corosync.conf.tmp"):
            os.unlink("corosync.conf.tmp")
        if os.path.exists("cluster.conf.tmp"):
            os.unlink("cluster.conf.tmp")

    def testNodeStandby(self):
        output, returnVal = pcs(temp_cib, "cluster standby rh7-1")
        ac(output, "")
        assert returnVal == 0

        # try to standby node which is already in standby mode
        output, returnVal = pcs(temp_cib, "cluster standby rh7-1")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "cluster unstandby rh7-1")
        ac(output, "")
        assert returnVal == 0

        # try to unstandby node which is no in standby mode
        output, returnVal = pcs(temp_cib, "cluster unstandby rh7-1")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "cluster standby nonexistant-node")
        assert returnVal == 1
        assert output == "Error: node 'nonexistant-node' does not appear to exist in configuration\n"

        output, returnVal = pcs(temp_cib, "cluster unstandby nonexistant-node")
        assert returnVal == 1
        assert output == "Error: node 'nonexistant-node' does not appear to exist in configuration\n"

    def testRemoteNode(self):
        o,r = pcs(temp_cib, "resource create D1 Dummy --no-default-ops")
        assert r==0 and o==""

        o,r = pcs(temp_cib, "resource create D2 Dummy --no-default-ops")
        assert r==0 and o==""

        o,r = pcs(temp_cib, "cluster remote-node rh7-2 D1")
        assert r==1 and o.startswith("\nUsage: pcs cluster remote-node")

        o,r = pcs(temp_cib, "cluster remote-node add rh7-2 D1")
        assert r==0 and o==""

        o,r = pcs(temp_cib, "cluster remote-node add rh7-1 D2 remote-port=100 remote-addr=400 remote-connect-timeout=50")
        assert r==0 and o==""

        o,r = pcs(temp_cib, "resource --full")
        assert r==0
        ac(o," Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n  Meta Attrs: remote-node=rh7-2 \n  Operations: monitor interval=60s (D1-monitor-interval-60s)\n Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n  Meta Attrs: remote-node=rh7-1 remote-port=100 remote-addr=400 remote-connect-timeout=50 \n  Operations: monitor interval=60s (D2-monitor-interval-60s)\n")

        o,r = pcs(temp_cib, "cluster remote-node remove")
        assert r==1 and o.startswith("\nUsage: pcs cluster remote-node")

        o,r = pcs(temp_cib, "cluster remote-node remove rh7-2")
        assert r==0 and o==""

        o,r = pcs(temp_cib, "cluster remote-node add rh7-2 NOTARESOURCE")
        assert r==1
        ac(o,"Error: unable to find resource 'NOTARESOURCE'\n")

        o,r = pcs(temp_cib, "cluster remote-node remove rh7-2")
        assert r==1
        ac(o,"Error: unable to remove: cannot find remote-node 'rh7-2'\n")

        o,r = pcs(temp_cib, "resource --full")
        assert r==0
        ac(o," Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (D1-monitor-interval-60s)\n Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n  Meta Attrs: remote-node=rh7-1 remote-port=100 remote-addr=400 remote-connect-timeout=50 \n  Operations: monitor interval=60s (D2-monitor-interval-60s)\n")

        o,r = pcs(temp_cib, "cluster remote-node remove rh7-1")
        assert r==0 and o==""

        o,r = pcs(temp_cib, "resource --full")
        assert r==0
        ac(o," Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (D1-monitor-interval-60s)\n Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (D2-monitor-interval-60s)\n")

    def test_cluster_setup_bad_args(self):
        output, returnVal = pcs(temp_cib, "cluster setup")
        self.assertEqual(
            "Error: A cluster name (--name <name>) is required to setup a cluster\n",
            output
        )
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "cluster setup --name cname")
        self.assertTrue(output.startswith("\nUsage: pcs cluster setup..."))
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "cluster setup cname rh7-1 rh7-2")
        self.assertEqual(
            "Error: A cluster name (--name <name>) is required to setup a cluster\n",
            output
        )
        self.assertEqual(1, returnVal)

    def test_cluster_setup_hostnames_resolving(self):
        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf=corosync.conf.tmp --cluster_conf=cluster.conf.tmp --name cname nonexistant-address"
        )
        ac(output, """\
Error: Unable to resolve all hostnames, use --force to override
Warning: Unable to resolve hostname: nonexistant-address
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf=corosync.conf.tmp --cluster_conf=cluster.conf.tmp --name cname nonexistant-address --force"
        )
        ac(output, """\
Warning: Unable to resolve hostname: nonexistant-address
""")
        self.assertEqual(0, returnVal)

    def test_cluster_setup_file_exists(self):
        if utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2"
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        corosync_conf = """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
"""
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, corosync_conf)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-2 rh7-3"
        )
        self.assertEqual("""\
Error: corosync.conf.tmp already exists, use --force to overwrite
""",
            output
        )
        self.assertEqual(1, returnVal)
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, corosync_conf)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --corosync_conf=corosync.conf.tmp --name cname rh7-2 rh7-3"
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-2
        nodeid: 1
    }

    node {
        ring0_addr: rh7-3
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_file_exists_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2"
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        cluster_conf = """\
<cluster config_version="9" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
"""
        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, cluster_conf)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-2 rh7-3"
        )
        self.assertEqual("""\
Error: cluster.conf.tmp already exists, use --force to overwrite
""",
            output
        )
        self.assertEqual(1, returnVal)
        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, cluster_conf)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --cluster_conf=cluster.conf.tmp --name cname rh7-2 rh7-3"
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="9" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-2" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-3" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-3"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

    def test_cluster_setup_2_nodes_no_atb(self):
        # Setup a 2 node cluster and make sure the two node config is set, then
        # add a node and make sure that it's unset, then remove a node and make
        # sure it's set again.
        if utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2"
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode add --corosync_conf=corosync.conf.tmp rh7-3"
        )
        self.assertEqual("rh7-3: successfully added!\n", output)
        self.assertEqual(0, returnVal)
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }

    node {
        ring0_addr: rh7-3
        nodeid: 3
    }
}

quorum {
    provider: corosync_votequorum
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode remove --corosync_conf=corosync.conf.tmp rh7-3"
        )
        self.assertEqual(0, returnVal)
        self.assertEqual("rh7-3: successfully removed!\n", output)
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode add --corosync_conf=corosync.conf.tmp rh7-3,192.168.1.3"
        )
        self.assertEqual("rh7-3,192.168.1.3: successfully added!\n", output)
        self.assertEqual(0, returnVal)
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }

    node {
        ring0_addr: rh7-3
        ring1_addr: 192.168.1.3
        nodeid: 3
    }
}

quorum {
    provider: corosync_votequorum
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode remove --corosync_conf=corosync.conf.tmp rh7-2"
        )
        self.assertEqual(0, returnVal)
        self.assertEqual("rh7-2: successfully removed!\n", output)
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-3
        ring1_addr: 192.168.1.3
        nodeid: 3
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode remove --corosync_conf=corosync.conf.tmp rh7-3,192.168.1.3"
        )
        self.assertEqual(0, returnVal)
        self.assertEqual("rh7-3,192.168.1.3: successfully removed!\n", output)
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }
}

quorum {
    provider: corosync_votequorum
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_2_nodes_with_atb(self):
        # Setup a 2 node cluster with auto_tie_breaker and make sure the two
        # node config is NOT set, then add a node, then remove a node and make
        # sure it is still NOT set.
        if utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --auto_tie_breaker=1"
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    auto_tie_breaker: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode add --corosync_conf=corosync.conf.tmp rh7-3"
        )
        self.assertEqual(output, "rh7-3: successfully added!\n")
        self.assertEqual(0, returnVal)
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }

    node {
        ring0_addr: rh7-3
        nodeid: 3
    }
}

quorum {
    provider: corosync_votequorum
    auto_tie_breaker: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode remove --corosync_conf=corosync.conf.tmp rh7-3"
        )
        self.assertEqual("rh7-3: successfully removed!\n", output)
        self.assertEqual(0, returnVal)
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    auto_tie_breaker: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_3_nodes(self):
        # Setup a 3 node cluster
        if utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 rh7-3"
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }

    node {
        ring0_addr: rh7-3
        nodeid: 3
    }
}

quorum {
    provider: corosync_votequorum
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_transport(self):
        # Test to make transport is set
        if utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --transport udp"
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udp
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_2_nodes_rhel6(self):
        # Setup a 2 node cluster and make sure the two node config is set, then
        # add a node and make sure that it's unset, then remove a node and make
        # sure it's set again.
        # There is no auto-tie-breaker in CMAN so we don't need the non-atb
        # variant as we do for corosync.
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="9" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode add --cluster_conf=cluster.conf.tmp rh7-3"
        )
        ac(output, "rh7-3: successfully added!\n")
        self.assertEqual(returnVal, 0)
        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="13" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-3" nodeid="3">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-3"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" transport="udp"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode remove --cluster_conf=cluster.conf.tmp rh7-3"
        )
        ac(output, "rh7-3: successfully removed!\n")
        self.assertEqual(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="15" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode add --cluster_conf=cluster.conf.tmp rh7-3,192.168.1.3"
        )
        ac(output, "rh7-3,192.168.1.3: successfully added!\n")
        self.assertEqual(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="20" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-3" nodeid="3">
      <altname name="192.168.1.3"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-3"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" transport="udp"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode remove --cluster_conf=cluster.conf.tmp rh7-2"
        )
        ac(output, "rh7-2: successfully removed!\n")
        self.assertEqual(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="22" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-3" nodeid="3">
      <altname name="192.168.1.3"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-3"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode remove --cluster_conf=cluster.conf.tmp rh7-3,192.168.1.3"
        )
        ac(output, "rh7-3,192.168.1.3: successfully removed!\n")
        self.assertEqual(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="23" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

    def test_cluster_setup_3_nodes_rhel6(self):
        # Setup a 3 node cluster
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 rh7-3"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="12" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-3" nodeid="3">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-3"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" transport="udp"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

    def test_cluster_setup_transport_rhel6(self):
        # Test to make transport is set
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --transport udpu"
        )
        ac(output, """\
Warning: Using udpu transport on a CMAN cluster, cluster restart is required after node add or remove
""")
        self.assertEqual(returnVal, 0)
        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="9" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udpu" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

    def test_cluster_setup_ipv6(self):
        if utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --ipv6"
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udpu
    ip_version: ipv6
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_ipv6_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --ipv6"
        )
        ac(output, """\
Warning: --ipv6 ignored as it is not supported on CMAN clusters
""")
        self.assertEqual(returnVal, 0)
        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="9" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

    def test_cluster_setup_rrp_passive_udp_addr01(self):
        if utils.is_rhel6():
            return

        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr0 1.1.2.0")
        assert r == 1
        ac(o, "Error: --addr0 can only be used once\n")

        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode blah --broadcast0 --transport udp")
        assert r == 1
        ac("Error: blah is an unknown RRP mode, use --force to override\n", o)

        o,r = pcs("cluster setup --transport udp --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0")
        ac(o,"")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udp
    rrp_mode: passive

    interface {
        ringnumber: 0
        bindnetaddr: 1.1.1.0
        mcastaddr: 239.255.1.1
        mcastport: 5405
    }

    interface {
        ringnumber: 1
        bindnetaddr: 1.1.2.0
        mcastaddr: 239.255.2.1
        mcastport: 5405
    }
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_rrp_passive_udp_addr01_mcast01(self):
        if utils.is_rhel6():
            return

        o,r = pcs("cluster setup --transport udp --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --mcast0 8.8.8.8 --addr1 1.1.2.0 --mcast1 9.9.9.9")
        ac(o,"")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udp
    rrp_mode: passive

    interface {
        ringnumber: 0
        bindnetaddr: 1.1.1.0
        mcastaddr: 8.8.8.8
        mcastport: 5405
    }

    interface {
        ringnumber: 1
        bindnetaddr: 1.1.2.0
        mcastaddr: 9.9.9.9
        mcastport: 5405
    }
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_rrp_passive_udp_addr01_mcastport01(self):
        if utils.is_rhel6():
            return

        o,r = pcs("cluster setup --transport udp --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --mcastport0 9999 --mcastport1 9998 --addr1 1.1.2.0")
        ac(o,"")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udp
    rrp_mode: passive

    interface {
        ringnumber: 0
        bindnetaddr: 1.1.1.0
        mcastaddr: 239.255.1.1
        mcastport: 9999
    }

    interface {
        ringnumber: 1
        bindnetaddr: 1.1.2.0
        mcastaddr: 239.255.2.1
        mcastport: 9998
    }
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_rrp_passive_udp_addr01_ttl01(self):
        if utils.is_rhel6():
            return

        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --ttl0 4 --ttl1 5 --transport udp")
        ac(o,"")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udp
    rrp_mode: passive

    interface {
        ringnumber: 0
        bindnetaddr: 1.1.1.0
        mcastaddr: 239.255.1.1
        mcastport: 5405
        ttl: 4
    }

    interface {
        ringnumber: 1
        bindnetaddr: 1.1.2.0
        mcastaddr: 239.255.2.1
        mcastport: 5405
        ttl: 5
    }
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_rrp_active_udp_addr01(self):
        if utils.is_rhel6():
            return

        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --transport udp")
        ac(o, "Error: using a RRP mode of 'active' is not supported or tested, use --force to override\n")
        assert r == 1

        o,r = pcs("cluster setup --force --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --transport udp")
        ac(o, "Warning: using a RRP mode of 'active' is not supported or tested\n")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udp
    rrp_mode: active

    interface {
        ringnumber: 0
        bindnetaddr: 1.1.1.0
        mcastaddr: 239.255.1.1
        mcastport: 5405
    }

    interface {
        ringnumber: 1
        bindnetaddr: 1.1.2.0
        mcastaddr: 239.255.2.1
        mcastport: 5405
    }
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_rrp_active_udp_broadcast_addr01(self):
        if utils.is_rhel6():
            return

        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --broadcast0 --transport udp")
        ac(o, "Error: using a RRP mode of 'active' is not supported or tested, use --force to override\n")
        assert r == 1

        o,r = pcs("cluster setup --force --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --broadcast0 --transport udp")
        ac(o, "Warning: using a RRP mode of 'active' is not supported or tested\n")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udp
    rrp_mode: active

    interface {
        ringnumber: 0
        bindnetaddr: 1.1.1.0
        broadcast: yes
    }

    interface {
        ringnumber: 1
        bindnetaddr: 1.1.2.0
        mcastaddr: 239.255.2.1
        mcastport: 5405
    }
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_rrp_udpu(self):
        if utils.is_rhel6():
            return

        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1,192.168.99.1 rh7-2,192.168.99.2,192.168.99.3")
        ac(o,"Error: You cannot specify more than two addresses for a node: rh7-2,192.168.99.2,192.168.99.3\n")
        assert r == 1

        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1,192.168.99.1 rh7-2")
        ac(o,"Error: if one node is configured for RRP, all nodes must be configured for RRP\n")
        assert r == 1

        o,r = pcs("cluster setup --force --local --name test99 rh7-1 rh7-2 --addr0 1.1.1.1")
        ac(o,"Error: --addr0 and --addr1 can only be used with --transport=udp\n")
        assert r == 1

        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1,192.168.99.1 rh7-2,192.168.99.2")
        ac(o,"")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: cname
    transport: udpu
    rrp_mode: passive
}

nodelist {
    node {
        ring0_addr: rh7-1
        ring1_addr: 192.168.99.1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        ring1_addr: 192.168.99.2
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_quorum_options(self):
        if utils.is_rhel6():
            return

        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name test99 rh7-1 rh7-2 --wait_for_all=2")
        ac(o, "Error: '2' is not a valid value for --wait_for_all, use 0 or 1\n")
        assert r == 1

        o,r = pcs("cluster setup --force --local --corosync_conf=corosync.conf.tmp --name test99 rh7-1 rh7-2 --wait_for_all=2")
        ac(o, "Error: '2' is not a valid value for --wait_for_all, use 0 or 1\n")
        assert r == 1

        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name test99 rh7-1 rh7-2 --auto_tie_breaker=2")
        ac(o, "Error: '2' is not a valid value for --auto_tie_breaker, use 0 or 1\n")
        assert r == 1

        o,r = pcs("cluster setup --force --local --corosync_conf=corosync.conf.tmp --name test99 rh7-1 rh7-2 --auto_tie_breaker=2")
        ac(o, "Error: '2' is not a valid value for --auto_tie_breaker, use 0 or 1\n")
        assert r == 1

        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name test99 rh7-1 rh7-2 --last_man_standing=2")
        ac(o, "Error: '2' is not a valid value for --last_man_standing, use 0 or 1\n")
        assert r == 1

        o,r = pcs("cluster setup --force --local --corosync_conf=corosync.conf.tmp --name test99 rh7-1 rh7-2 --last_man_standing=2")
        ac(o, "Error: '2' is not a valid value for --last_man_standing, use 0 or 1\n")
        assert r == 1

        o,r = pcs("cluster setup --force --local --corosync_conf=corosync.conf.tmp --name test99 rh7-1 rh7-2 --wait_for_all=1 --auto_tie_breaker=1 --last_man_standing=1 --last_man_standing_window=12000")
        ac(o,"")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: test99
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    wait_for_all: 1
    auto_tie_breaker: 1
    last_man_standing: 1
    last_man_standing_window: 12000
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_rrp_passive_udp_addr01_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr0 1.1.2.0"
        )
        ac(output, "Error: --addr0 can only be used once\n")
        self.assertEqual(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode blah --broadcast0 --transport udp"
        )
        ac(output, """\
Error: blah is an unknown RRP mode, use --force to override
Warning: Enabling broadcast for ring 1 as CMAN does not support broadcast in only one ring
""")
        self.assertEqual(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --transport udp --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="14" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1">
    <multicast addr="239.255.1.1"/>
    <altmulticast addr="239.255.2.1"/>
  </cman>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
  <totem rrp_mode="passive"/>
</cluster>
""")

    def test_cluster_setup_rrp_passive_udp_addr01_mcast01_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --transport udp --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --mcast0 8.8.8.8 --addr1 1.1.2.0 --mcast1 9.9.9.9"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="14" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1">
    <multicast addr="8.8.8.8"/>
    <altmulticast addr="9.9.9.9"/>
  </cman>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
  <totem rrp_mode="passive"/>
</cluster>
""")

    def test_cluster_setup_rrp_passive_udp_addr01_mcastport01_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --transport udp --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --mcastport0 9999 --mcastport1 9998 --addr1 1.1.2.0"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="14" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1">
    <multicast addr="239.255.1.1" port="9999"/>
    <altmulticast addr="239.255.2.1" port="9998"/>
  </cman>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
  <totem rrp_mode="passive"/>
</cluster>
""")

    def test_cluster_setup_rrp_passive_udp_addr01_ttl01_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --ttl0 4 --ttl1 5 --transport udp"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="14" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1">
    <multicast addr="239.255.1.1" ttl="4"/>
    <altmulticast addr="239.255.2.1" ttl="5"/>
  </cman>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
  <totem rrp_mode="passive"/>
</cluster>
""")

    def test_cluster_setup_rrp_active_udp_addr01_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --transport udp"
        )
        ac(
            output,
            "Error: using a RRP mode of 'active' is not supported or tested, use --force to override\n"
        )
        self.assertEqual(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --transport udp"
        )
        ac(
            output,
            "Warning: using a RRP mode of 'active' is not supported or tested\n"
        )
        self.assertEqual(returnVal, 0)
        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="14" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1">
    <multicast addr="239.255.1.1"/>
    <altmulticast addr="239.255.2.1"/>
  </cman>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
  <totem rrp_mode="active"/>
</cluster>
""")

    def test_cluster_setup_rrp_active_udp_broadcast_addr01_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --broadcast0 --transport udp"
        )
        ac(output, """\
Error: using a RRP mode of 'active' is not supported or tested, use --force to override
Warning: Enabling broadcast for ring 1 as CMAN does not support broadcast in only one ring
""")
        self.assertEqual(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --broadcast0 --transport udp"
        )
        ac(output, """\
Warning: Enabling broadcast for ring 1 as CMAN does not support broadcast in only one ring
Warning: using a RRP mode of 'active' is not supported or tested
""")
        self.assertEqual(returnVal, 0)
        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="12" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="yes" expected_votes="1" transport="udpb" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
  <totem rrp_mode="active"/>
</cluster>
""")

    def test_cluster_setup_rrp_udpu_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-1,192.168.99.1 rh7-2,192.168.99.2,192.168.99.3"
        )
        ac(output, """\
Error: You cannot specify more than two addresses for a node: rh7-2,192.168.99.2,192.168.99.3
""")
        self.assertEqual(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --name cname rh7-1,192.168.99.1 rh7-2"
        )
        ac(output, """\
Error: if one node is configured for RRP, all nodes must be configured for RRP
""")
        self.assertEqual(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --name test99 rh7-1 rh7-2 --addr0 1.1.1.1 --transport=udpu"
        )
        ac(output, """\
Error: --addr0 and --addr1 can only be used with --transport=udp
Warning: Using udpu transport on a CMAN cluster, cluster restart is required after node add or remove
""")
        self.assertEqual(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-1,192.168.99.1 rh7-2,192.168.99.2"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="12" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <altname name="192.168.99.1"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <altname name="192.168.99.2"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
  <totem rrp_mode="passive"/>
</cluster>
""")

    def test_cluster_setup_broadcast_rhel6(self):
        if not utils.is_rhel6():
            return

        cluster_conf = """\
<cluster config_version="12" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="yes" expected_votes="1" transport="udpb" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
  <totem rrp_mode="passive"/>
</cluster>
"""

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode passive --broadcast0 --transport udp"
        )
        ac(output, """\
Warning: Enabling broadcast for ring 1 as CMAN does not support broadcast in only one ring
""")
        self.assertEqual(returnVal, 0)
        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, cluster_conf)

        os.remove("cluster.conf.tmp")

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --broadcast0 --transport udp"
        )
        ac(output, """\
Warning: Enabling broadcast for ring 1 as CMAN does not support broadcast in only one ring
""")
        self.assertEqual(returnVal, 0)
        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, cluster_conf)

    def test_cluster_setup_quorum_options_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name test99 rh7-1 rh7-2 --wait_for_all=2 --auto_tie_breaker=3 --last_man_standing=4 --last_man_standing_window=5"
        )
        ac(output, """\
Warning: --wait_for_all ignored as it is not supported on CMAN clusters
Warning: --auto_tie_breaker ignored as it is not supported on CMAN clusters
Warning: --last_man_standing ignored as it is not supported on CMAN clusters
Warning: --last_man_standing_window ignored as it is not supported on CMAN clusters
""")
        self.assertEqual(returnVal, 0)
        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="9" name="test99">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

    def test_cluster_setup_totem_options(self):
        if utils.is_rhel6():
            return

        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name test99 rh7-1 rh7-2 --token 20000 --join 20001 --consensus 20002 --miss_count_const 20003 --fail_recv_const 20004 --token_coefficient 20005")
        ac(o,"")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    secauth: off
    cluster_name: test99
    transport: udpu
    token: 20000
    token_coefficient: 20005
    join: 20001
    consensus: 20002
    miss_count_const: 20003
    fail_recv_const: 20004
}

nodelist {
    node {
        ring0_addr: rh7-1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_totem_options_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name test99 rh7-1 rh7-2 --token 20000 --join 20001 --consensus 20002 --miss_count_const 20003 --fail_recv_const 20004 --token_coefficient 20005")
        ac(output, """\
Warning: --token_coefficient ignored as it is not supported on CMAN clusters
""")
        self.assertEqual(returnVal, 0)
        with open("cluster.conf.tmp") as f:
            data = f.read()
            ac(data, """\
<cluster config_version="10" name="test99">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
  <totem consensus="20002" fail_recv_const="20004" join="20001" miss_count_const="20003" token="20000"/>
</cluster>
""")

    def testUIDGID(self):
        if utils.is_rhel6():
            os.system("cp cluster.conf cluster.conf.tmp")

            o,r = pcs("cluster uidgid --cluster_conf=cluster.conf.tmp")
            assert r == 0
            ac(o, "No uidgids configured in cluster.conf\n")

            o,r = pcs("cluster uidgid blah --cluster_conf=cluster.conf.tmp")
            assert r == 1
            assert o.startswith("\nUsage:")

            o,r = pcs("cluster uidgid rm --cluster_conf=cluster.conf.tmp")
            assert r == 1
            assert o.startswith("\nUsage:")

            o,r = pcs("cluster uidgid add --cluster_conf=cluster.conf.tmp")
            assert r == 1
            assert o.startswith("\nUsage:")

            o,r = pcs("cluster uidgid add blah --cluster_conf=cluster.conf.tmp")
            assert r == 1
            ac(o, "Error: uidgid options must be of the form uid=<uid> gid=<gid>\n")

            o,r = pcs("cluster uidgid rm blah --cluster_conf=cluster.conf.tmp")
            assert r == 1
            ac(o, "Error: uidgid options must be of the form uid=<uid> gid=<gid>\n")

            o,r = pcs("cluster uidgid add uid=zzz --cluster_conf=cluster.conf.tmp")
            assert r == 0
            ac(o, "")

            o,r = pcs("cluster uidgid add uid=zzz --cluster_conf=cluster.conf.tmp")
            assert r == 1
            ac(o, "Error: unable to add uidgid\nError: uidgid entry already exists with uid=zzz, gid=\n")

            o,r = pcs("cluster uidgid add gid=yyy --cluster_conf=cluster.conf.tmp")
            assert r == 0
            ac(o, "")

            o,r = pcs("cluster uidgid add uid=aaa gid=bbb --cluster_conf=cluster.conf.tmp")
            assert r == 0
            ac(o, "")

            o,r = pcs("cluster uidgid --cluster_conf=cluster.conf.tmp")
            assert r == 0
            ac(o, "UID/GID: gid=, uid=zzz\nUID/GID: gid=yyy, uid=\nUID/GID: gid=bbb, uid=aaa\n")

            o,r = pcs("cluster uidgid rm gid=bbb --cluster_conf=cluster.conf.tmp")
            assert r == 1
            ac(o, "Error: unable to remove uidgid\nError: unable to find uidgid with uid=, gid=bbb\n")

            o,r = pcs("cluster uidgid rm uid=aaa gid=bbb --cluster_conf=cluster.conf.tmp")
            assert r == 0
            ac(o, "")

            o,r = pcs("cluster uidgid --cluster_conf=cluster.conf.tmp")
            assert r == 0
            ac(o, "UID/GID: gid=, uid=zzz\nUID/GID: gid=yyy, uid=\n")

            o,r = pcs("cluster uidgid rm uid=zzz --cluster_conf=cluster.conf.tmp")
            assert r == 0
            ac(o, "")

            o,r = pcs("config --cluster_conf=cluster.conf.tmp")
            assert r == 0
            assert o.find("UID/GID: gid=yyy, uid=") != -1

            o,r = pcs("cluster uidgid rm gid=yyy --cluster_conf=cluster.conf.tmp")
            assert r == 0
            ac(o, "")

            o,r = pcs("config --cluster_conf=cluster.conf.tmp")
            assert r == 0
            assert o.find("No uidgids") == -1
        else:
            o,r = pcs("cluster uidgid")
            assert r == 0
            ac(o, "No uidgids configured in cluster.conf\n")

            o,r = pcs("cluster uidgid add")
            assert r == 1
            assert o.startswith("\nUsage:")

            o,r = pcs("cluster uidgid rm")
            assert r == 1
            assert o.startswith("\nUsage:")

            o,r = pcs("cluster uidgid xx")
            assert r == 1
            assert o.startswith("\nUsage:")

            o,r = pcs("cluster uidgid add uid=testuid gid=testgid")
            assert r == 0
            ac(o, "")

            o,r = pcs("cluster uidgid add uid=testuid gid=testgid")
            assert r == 1
            ac(o, "Error: uidgid file with uid=testuid and gid=testgid already exists\n")

            o,r = pcs("cluster uidgid rm uid=testuid2 gid=testgid2")
            assert r == 1
            ac(o, "Error: no uidgid files with uid=testuid2 and gid=testgid2 found\n")

            o,r = pcs("cluster uidgid rm uid=testuid gid=testgid2")
            assert r == 1
            ac(o, "Error: no uidgid files with uid=testuid and gid=testgid2 found\n")

            o,r = pcs("cluster uidgid rm uid=testuid2 gid=testgid")
            assert r == 1
            ac(o, "Error: no uidgid files with uid=testuid2 and gid=testgid found\n")

            o,r = pcs("cluster uidgid")
            assert r == 0
            ac(o, "UID/GID: uid=testuid gid=testgid\n")

            o,r = pcs("cluster uidgid rm uid=testuid gid=testgid")
            assert r == 0
            ac(o, "")

            o,r = pcs("cluster uidgid")
            assert r == 0
            ac(o, "No uidgids configured in cluster.conf\n")

    def testClusterUpgrade(self):
        if not isMinimumPacemakerVersion(1,1,11):
            print("WARNING: Unable to test cluster upgrade because pacemaker is older than 1.1.11")
            return
        with open(temp_cib) as myfile:
            data = myfile.read()
            assert data.find("pacemaker-1.2") != -1
            assert data.find("pacemaker-2.") == -1

        o,r = pcs("cluster cib-upgrade")
        ac(o,"Cluster CIB has been upgraded to latest version\n")
        assert r == 0

        with open(temp_cib) as myfile:
            data = myfile.read()
            assert data.find("pacemaker-1.2") == -1
            assert data.find("pacemaker-2.") != -1

        o,r = pcs("cluster cib-upgrade")
        ac(o,"Cluster CIB has been upgraded to latest version\n")
        assert r == 0

    def test_can_not_setup_cluster_for_unknown_transport_type(self):
        self.assert_pcs_fail(
            'cluster setup --local --corosync_conf=corosync.conf.tmp'
                +" --name cname rh7-1,192.168.99.1 rh7-2,192.168.99.2"
                +" --transport=unknown"
            ,
            "Error: unknown transport 'unknown', use --force to override\n"
        )

class PrepareNodeNamesTest(unittest.TestCase):
    def test_return_original_when_is_in_pacemaker_nodes(self):
        node = 'test'
        self.assertEqual(
            node,
            cluster.prepare_node_name(node, {1: node}, {})
        )

    def test_return_original_when_is_not_in_corosync_nodes(self):
        node = 'test'
        self.assertEqual(
            node,
            cluster.prepare_node_name(node, {}, {})
        )

    def test_return_original_when_corosync_id_not_in_pacemaker(self):
        node = 'test'
        self.assertEqual(
            node,
            cluster.prepare_node_name(node, {}, {1: node})
        )

    def test_return_modified_name(self):
        node = 'test'
        self.assertEqual(
            'another (test)',
            cluster.prepare_node_name(node, {1: 'another'}, {1: node})
        )

    def test_return_modified_name_with_pm_null_case(self):
        node = 'test'
        self.assertEqual(
            '*Unknown* (test)',
            cluster.prepare_node_name(node, {1: '(null)'}, {1: node})
        )

class NodeActionTaskTest(unittest.TestCase):
    def test_can_run_action(self):
        def action(node, arg, kwarg=None):
            return (0, ':'.join([node, arg, kwarg]))

        report_list = []
        def report(node, returncode, output):
            report_list.append('|'.join([node, str(returncode), output]))

        task = NodeActionTask(report, action, 'node', 'arg', kwarg='kwarg')
        task()

        self.assertEqual(['node|0|node:arg:kwarg'], report_list)
        self.assertEqual(0, task.returncode)


if __name__ == "__main__":
    unittest.main()

