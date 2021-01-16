# ZHE2 to ZHE3 Migration for ZenHub for Kubernetes

## Table of Contents
- [When am I ready to migrate production?](#when-am-i-ready-to-migrate)
- [Migration overview](#migration-overview)
- [Gather the data from your existing ZHE2 source instance](#gather-the-data-from-your-existing-zhe2-source-instance)
- [Move the data to your jump box or workstation](#move-the-data-to-your-jump-box-or-workstation)
- [Upload the data to the DBs and bucket](#upload-the-data-to-the-dbs-and-bucket)
  - [MongoDB](#mongodb)
  - [PostgreSQL](#postgresql)
  - [Update the references in the MongoDB blob collection](#update-the-references-in-the-mongodb-blob-collection)
  - [Upload files and images to the object storage bucket](#upload-files-and-images-to-the-object-storage-bucket)

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
├── file_types.json
├── mongo.tar.gz
├── postgres_raptor_data.dump
├── uploads.tar.gz
└── variables.txt
```
- `file_types.json`: an array MIME types for the uploaded files, used when uploading to the object storage bucket
- `mongo.tar.gz`: the MongoDB data dump
- `postgres_raptor_data.dump`: the PostgreSQL data dump
- `uploads.tar.gz`: all files and images uploaded to GitHub issues through ZenHub
- `variables.txt`: a list of environment variables you can use to help fill out fields in your `kustomization.yaml`.

### Upload the data to the DBs and bucket

For these examples, we will assume that your workstation or jump box has network access to your MongoDB and PostgreSQL databases as well as your object storage bucket.

#### MongoDB

To restore the MongoDB dump we will need to have the MongoDB tools on your workstation/jumpbox.

1. Install MongoDB tools

```bash
brew install mongodb/brew/mongosh
brew install mongodb/brew/mongodb-database-tools
```
> Note: `mongosh` is the Mongo shell, and `mongodb-database-tools` includes `mongorestore`.

2. Download your MongoDB provider's CA certificate. For example, if using Amazon DocumentDB, you can find it [here](https://docs.aws.amazon.com/documentdb/latest/developerguide/connect_programmatically.html#connect_programmatically-tls_enabled). This will ensure the MongoDB tools can verify the certificate of your MongoDB server.

3. Create a restorer user on the zenhub DB

Depending on the authentication and authorization system of your MongoDB provider, you may have to adjust these steps. In most systems, you will need to create a database user that has both `readWrite` and `dbAdmin` permissions to successfully restore the database.

```
mongo --ssl --sslCAFile <path/to/mongo-ca-cert.pem> --username root --host zenhub-mongo.example.com --port 27017
```
>Note: You will be prompted for `--username`'s password.

```
use zenhub
db.createUser({user: "restorer", pwd: "the-restorer-password", roles: [ "readWrite", "dbAdmin" ]})
```
>Note: If you have already deployed ZenHub to your Kubernetes cluster and it has successfully connected to Mongo, the `zenhub` database should exist.

4. Expand the Mongo tarball

```bash
tar -xf mongo.tar.gz
```

5. Restore the Mongo database

```bash
mongorestore --nsFrom='zenhub_enterprise.*' --nsTo='zenhub.*' --stopOnError --drop --ssl --sslCAFile <path/to/mongo-ca-cert.pem> --host zenhub-mongo.example.com --port 27017 --username restorer --db zenhub ./dump/zenhub_enterprise
```

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

2. Set the required env vars (again replace the bucket URLs)

```bash
export REMOTE_FILES_URL=https://zhe2migration-test.s3.us-east-1.amazonaws.com
export REMOTE_IMAGES_URL=https://zhe2migration-test-images.s3.us-east-1.amazonaws.com
```

3. Run the migration script. This is *technically* not needed for the files to appear correctly, but it ensures that the blob data in MongoDB is correct.

```bash
node /zenhub/app/scripts/zhe/migrateBlobsToRemoteUrls.js
```

#### Upload files and images to the object storage bucket

> Instructions coming soon.