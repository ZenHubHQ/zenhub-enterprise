# ZHE for K8s Support Bundle Script

This script uses kubectl to gather information about the Zenhub instance deployed on the cluster. It writes this information into files and packages them into a TAR archive that you can send to us. This script does not cause any downtime and can be run without putting Zenhub in maintenance mode.

### Prerequisites
- Must be connected to the ZHE K8s cluster
- kubectl must be installed on the machine that will run the script
- Metrics server enabled on the cluster (optional)

### Usage
From this directory, run this command, replacing `<zenhub-namespace>` with the namespace Zenhub is deployed in.

```
chmod +x ./support_bundle.sh && ./support_bundle.sh -n <zenhub-namespace>
```
