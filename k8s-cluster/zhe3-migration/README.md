# ZHE2 to ZHE3 Migration for ZenHub for Kubernetes

## Table of Contents
- [When am I ready to migrate production?](#when-am-i-ready-to-migrate-production)
- [Migration overview](#migration-overview)
- [Gather the data from your existing ZHE2 source instance](#gather-the-data-from-your-existing-zhe2-source-instance)
- [Move the data to your jump box or workstation](#move-the-data-to-your-jump-box-or-workstation)
- [Upload the data to the DBs](#upload-the-data-to-the-dbs)
  - [MongoDB](#mongodb)
  - [PostgreSQL](#postgresql)
  - [Update the references in the MongoDB blob collection](#update-the-references-in-the-mongodb-blob-collection)
- [Upload the files and images to the buckets](#upload-the-files-and-images-to-the-buckets)


### When am I ready to migrate production?

By its nature, the migration of ZenHub to the new ZHE3 infrastructure is a complex process. For this reason, it is important to validate the migration as much as possible before migrating your production ZenHub deployment to minimize downtime for users and decrease the probability of issues occurring.

Before planning a production migration, we recommend that customers have achieved the following milestones:
- Have successfully deployed ZenHub to a "production landing zone" environment ✅
- Have successfully performed at least one full data migration to your "production landing zone" environment ✅

In this case, the landing zone will be the Kubernetes cluster and namespace, external databases etc. with all of your production settings, but without doing the final step of cutting over your ZenHub DNS record to the new deployment.

### Migration overview

The migration of your ZenHub data has 3 major steps.

1. **Gather** the data from your existing ZHE2 source instance.
2. **Move** the data to a jump box or workstation with network access to your new MongoDB, PostgreSQL, and bucket targets.
3. **Upload** the data to each target.

The steps below will outline how to make secure connections with the MongoDB and PostgreSQL databases, as well as the object storage bucket to migrate your data. Our examples demonstrate the migration process using a Macbook workstation. You might use a jumpbox or a different OS on your workstation, but the steps will be similar. Please reach out to ZenHub Support if you have any problems with the migration. These steps will assume that TLS has been enabled on your database servers already, as is likely the case if you use a database-as-a-service provider.

### Gather the data from your existing ZHE2 source instance

1. SSH to your existing ZHE2 source instance.
2. Download the `zhe3-migration-cluster.sh` script from this folder to your existing ZHE2 instance.
3. Run the script (note: this will dump the databases which may impact performance for the duration).

```bash
sudo ./zhe3-migration-cluster.sh
```

### Move the data to your jump box or workstation

1. Using `scp` or your chosen tool, move your `migration-data-<timestamp>.tar.gz` bundle to the workstation or jumpbox from which you will restore the data to your cluster.

2. Unzip your `migration-data-<timestamp>.tar.gz`

```bash
tar -xf migration-data-<timestamp>.tar.gz
```

You should end up with the following files:
```
.
├── mongo.tar.gz
├── postgres_raptor_data.dump
├── uploads.tar.gz
└── variables.txt
```
- `mongo.tar.gz`: the MongoDB data dump
- `postgres_raptor_data.dump`: the PostgreSQL data dump
- `uploads.tar.gz`: all files and images uploaded to GitHub issues through ZenHub
- `variables.txt`: a list of environment variables you can use to help fill out fields in your `kustomization.yaml`.

### Upload the data to the DBs and bucket

For these examples, we will assume that your workstation or jump box has network access to your MongoDB and PostgreSQL databases as well as your object storage bucket.

> ⚠️ **NOTE:** If you do not have direct access to the databases, another method to upload the database data is to run temporary MongoDB and PostgreSQL pods in your K8s namespace and use them as a jump box, as these will also already have the required tools installed.

#### MongoDB

To restore the MongoDB dump we will need to have the MongoDB tools on your workstation/jumpbox.

1. Install MongoDB tools

```bash
brew install mongodb/brew/mongosh
brew install mongodb/brew/mongodb-database-tools
```
> ⚠️ **NOTE:** `mongosh` is the Mongo shell, and `mongodb-database-tools` includes `mongorestore`.

2. Download your MongoDB provider's CA certificate. For example, if using Amazon DocumentDB, you can find it [here](https://docs.aws.amazon.com/documentdb/latest/developerguide/connect_programmatically.html#connect_programmatically-tls_enabled). This will ensure the MongoDB tools can verify the certificate of your MongoDB server.

3. Create a restorer user on the zenhub DB

Depending on the authentication and authorization system of your MongoDB provider, you may have to adjust these steps. In most systems, you will need to create a database user that has both `readWrite` and `dbAdmin` permissions to successfully restore the database.

```
mongo --ssl --sslCAFile <path/to/mongo-ca-cert.pem> --username root --host zenhub-mongo.example.com --port 27017
```
> ⚠️ **NOTE:** You will be prompted for `--username`'s password.

```
use zenhub
db.createUser({user: "restorer", pwd: "the-restorer-password", roles: [ "readWrite", "dbAdmin" ]})
```
> ⚠️ **NOTE:** If you have already deployed ZenHub to your Kubernetes cluster and it has successfully connected to Mongo, the `zenhub` database should exist.

4. Expand the Mongo tarball

```bash
tar -xf mongo.tar.gz
```

5. Restore the Mongo database

```bash
mongorestore --nsFrom='zenhub_enterprise.*' --nsTo='zenhub.*' --stopOnError --drop --ssl --sslCAFile <path/to/mongo-ca-cert.pem> --host zenhub-mongo.example.com --port 27017 --username restorer --db zenhub ./dump/zenhub_enterprise
```

> ⚠️ **NOTE:** If you are using Amazon DocumentDB, add the `--noIndexRestore` option, as DocumentDB requires shorter index names. With this option, the application will rebuild the indexes as needed with the shorter names.

#### PostgreSQL

To restore the PostgreSQL dump we will need to have the PostgreSQL tools on your workstation/jumpbox. Install the latest PostgreSQL version 11 tools.

1. Install PostgreSQL tools

```bash
brew install postgresql@11
```

2. Download your PostgreSQL provider's CA certificate. For example, if you're using Amazon RDS, you can find it [here](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html).

3. Restore the DB

```bash
pg_restore --clean --no-owner -v -h localhost -p 5432 -d raptor_production -U postgres -W --sslrootcert=<path/to/postgres-ca-cert.pem> --sslmode=verify-full postgres_raptor_data.dump
```

#### Update the references in the MongoDB blob collection

MongoDB stores the location of each file object uploaded to ZenHub. Since these have moved to your new bucket, we need to update these references in the database.

1. Open a terminal to the toad api pod (replace `zhe2migration` and `toad-api-544dc6576c-f2kp4` with the name of your namespace and pod)

```bash
kubectl -n zhe2migration exec -it toad-api-544dc6576c-f2kp4 -- bash
```

2. Set the required env vars (again replace the bucket URLs with your own)

```bash
export REMOTE_FILES_URL=https://zhe2migration-test.s3.us-east-1.amazonaws.com
export REMOTE_IMAGES_URL=https://zhe2migration-test-images.s3.us-east-1.amazonaws.com
```

3. Run the migration script

```bash
node /zenhub/app/scripts/zhe/migrateBlobsToRemoteUrls.js
```

### Upload files and images to the object storage bucket
Inside of your migration data bundle is another bundle called `uploads.tar.gz`. This contains the files and images uploaded to GitHub issues through the ZenHub web app. To upload these, we will use a third-party tool that can interact with any bucket that implements the S3 API: [s3cmd](https://s3tools.org/s3cmd).

1. Install s3cmd and libmagic

To install s3cmd, you will need to have Python 2.6 (or newer) installed. For more information on ways to download and install s3cmd, please visit [s3tools.org](https://s3tools.org/download) or [GitHub](https://github.com/s3tools/s3cmd/blob/master/INSTALL.md).

```bash
pip install s3cmd
```

The **libmagic** library is essential for s3cmd to detect and upload the correct MIME type for each file to the bucket metadata.

```bash
brew install libmagic
```

2. Configure s3cmd

To use s3cmd it needs to be configured with your S3/HMAC credentials. To configure s3cmd, you will need:
- Access key
- Secret key
- Region
- S3 Endpoint (for non-Amazon buckets that implement the S3 API, this will be their S3 API endpoint) e.g.: `s3.us-east.cloud-object-storage.appdomain.cloud`
- DNS-style bucket+hostname:port template for accessing a bucket, e.g.: `%(bucket)s.s3.us-east.cloud-object-storage.appdomain.cloud`
- Encryption password (use any)
- Path to GPG program [None]
- Use HTTPS protocol [Yes]
- HTTP Proxy server name (use if you can't access S3 directly from your workstation/jump box)

```bash
s3cmd --configure
```
Your settings will be stored by default at `$HOME/.s3cfg`. You can test if you can access your buckets with the configured credentials with `s3cmd ls`.

3. Expand `uploads.tar.gz`

```bash
tar -xf uploads.tar.gz
```
The `uploads.tar.gz` tarball will expand into the following structure, with more files and folders under `files` and `images`:
```
├── data
│   └── uploads
│       ├── files
│       └── images
```

4. Sync the local directories to the buckets (replace the s3 paths with your own)

```bash
s3cmd sync data/uploads/files/* s3://zenhub-files
s3cmd sync data/uploads/images/* s3://zenhub-images
```
> ⚠️ **NOTE:** If you see "`WARNING: Module python-magic is not available. Guessing MIME types based on file extensions`", then you do not have libmagic installed correctly and the MIME types won't be set. You will need to install libmagic, delete all objects, and sync again.

Congrats! 🎉 All of your data should now be migrated and ready to use in ZHE3.