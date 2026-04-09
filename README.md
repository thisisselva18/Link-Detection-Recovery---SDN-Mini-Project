# SDN Mini Project

## Link Failure Detection and Recovery using Mininet + Ryu

---

## 📌 Problem Statement

Design and implement an SDN-based system that detects link failures and dynamically reroutes traffic using a centralized controller.

---

## 🎯 Objective

* Detect link failures using topology events
* Compute alternate paths dynamically (Dijkstra)
* Install OpenFlow rules (FLOW_MOD)
* Maintain connectivity during failures

---

## 🏗️ Network Topology

```
           h1 (10.0.0.1)
                |
               s1
             /    \
           s3 ---- s2
                     |
               h2 (10.0.0.2)
```

### Explanation

* **Primary path:** s1 → s2
* **Backup path:** s1 → s3 → s2
* Enables automatic rerouting during link failure

---

## ⚙️ Requirements

Install dependencies:

```bash
sudo apt update
sudo apt install mininet python3-ryu wireshark iperf3
pip install networkx
```

---

## 🚀 Execution Steps

### 🖥️ Terminal 1: Start Ryu Controller

```bash
source ryu-env/bin/activate
ryu-manager link_failcontroller.py --observe-links
```

Expected logs:

```
Link UP: 0x1 -> 0x2
Host learned: 00:00:00:00:00:01 at 0x1
Installing flow on 0x1 ...
```

---

### 🖥️ Terminal 2: Start Mininet

```bash
sudo mn --custom topo_linkfail.py --topo mytopo --controller=remote
```

---

## 🧪 TEST CASE 1: Normal Operation

### Run:

```bash
mininet> pingall
```

### Expected:

* ✅ Ping SUCCESS
* ✅ Flow rules installed
* ✅ Controller logs paths

---

## 🧪 TEST CASE 2: Link Failure & Recovery

### Step 1: Bring link down

```bash
mininet> link s1 s2 down
```

### Step 2: Test connectivity

```bash
mininet> pingall
```

### Expected:

* ⚠️ Few packet drops
* ✅ Traffic rerouted via s1 → s3 → s2
* ✅ Controller logs:

```
🔥 LINK DOWN: 0x1 -> 0x2
Path ... -> 0x1 -> 0x3 -> 0x2
```

### Step 3: Restore link

```bash
mininet> link s1 s2 up
```

---


## 📊 Flow Table Verification

Run in **new terminal (outside Mininet):**

```bash
sudo ovs-ofctl dump-flows s1
sudo ovs-ofctl dump-flows s2
sudo ovs-ofctl dump-flows s3
```

### Expected:

```
priority=10, eth_src=..., eth_dst=..., actions=output:PORT
```

## 📡 Wireshark Analysis

### Steps:

1. Select interface: `lo`
2. Apply filter:

```
tcp.port == 6653
```

## 🔥 Key Features

* Dynamic shortest path routing using NetworkX
* Real-time topology discovery
* Automatic failover mechanism
* Flow rule installation using OpenFlow 1.3

---

## 🧠 Working Logic

1. Switch sends **Packet-In**
2. Controller learns host locations
3. Shortest path computed using graph
4. Controller sends **FLOW_MOD**
5. Switch forwards packets directly

---

## 🎯 Conclusion

The system successfully:

* Detects link failures
* Computes alternate paths
* Maintains connectivity
* Minimizes packet loss

---