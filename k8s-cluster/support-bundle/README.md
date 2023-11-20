# ZHE for K8s Support Bundle

This script uses Kubectl to gather information about the Zenhub instance deployed on the cluster. It writes this information into files and packages them into a TAR archive that you can send to us.

This script does not cause any downtime and can be run without putting Zenhub in maintenance mode.

### Prerequisites
- Must be connected to the ZHE K8s cluster
- Kubectl must be installed on the machine that will run the script
- Metrics server enabled on the cluster (optional)

### Usage
From this directory, run this command, replacing `<zenhub-namespace>` with the namespace Zenhub is deployed in.

```
chmod +x ./support_bundle.sh && ./support_bundle.sh -n <zenhub-namespace>
```

## Uploading the Support Bundle

We have prepared a Python script that you can use to send us your support bundle. The script uploads the file to our secure Amazon S3 Bucket that can only be accessed by certain Zenhub employees who work on supporting Zenhub Enterprise. The bundle will be retained for a maximum of 60 days before being automatically deleted from the bucket.

### Prerequisites
- Must have a support bundle already generated that you want to upload
- Python 3 with the boto3 and PyYaml packages installed
- Contact Zenhub Support to request a set of access keys, then set them in the environment

```bash
export SUPPORT_BUNDLE_ACCESS_KEY=<supplied_by_zenhub_support>
export SUPPORT_BUNDLE_SECRET_KEY=<supplied_by_zenhub_support>
```

```bash
pip install -r requirements.txt
```

### Usage
From this directory, run the `upload_bundle.py` script like so:
- Replace `<customer_identifier>` with an identifier to distinguish your support bundle from others
- Replace `<support_bundle_file_path>` with the full path to the tar you want to upload

```bash
python3 upload_bundle.py <customer_identifier> <support_bundle_file_path>
```

Then contact Zenhub Enterprise Support with a description of your problem and the name of your support bundle.
