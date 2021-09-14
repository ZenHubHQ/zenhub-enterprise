# ZHE2 to ZHE3 Migration for ZenHub for Kubernetes

## Table of Contents
- [When am I ready to migrate production?](#when-am-i-ready-to-migrate-production)
- [Migration overview](#migration-overview)
- [Testing the migration](#testing-the-migration)
  - [Choose a subdomain for the test](#choose-a-subdomain-for-the-test)
  - [Configure a temporary OAuth app](#configure-a-temporary-oauth-app)
  - [(Re)Deploy your application](#redeploy-your-application)
  - [Follow the Migration steps](#follow-the-migration-steps)
  - [Return to production config](#return-to-production-config)
- [Migration steps](#migration-steps)
  - [Gather the data from your existing ZHE2 source instance](#gather-the-data-from-your-existing-zhe2-source-instance)
  - [Move the data to your jump box or workstation](#move-the-data-to-your-jump-box-or-workstation)
  - [Upload the data to the DBs](#upload-the-data-to-the-dbs)
    - [MongoDB](#mongodb)
    - [PostgreSQL](#postgresql)
  - [Update the references in the MongoDB blob collection](#update-the-references-in-the-mongodb-blob-collection)
  - [Upload files and images to the object storage buckets](#upload-files-and-images-to-the-object-storage-buckets)


## When am I ready to migrate production?

By its nature, the migration of ZenHub to the new ZHE3 infrastructure is a complex process. For this reason, it is important to validate the migration as much as possible before migrating your production ZenHub deployment to minimize downtime for users and decrease the probability of issues occurring.

Before planning a production migration, we recommend that customers have achieved the following milestones:
- Have successfully deployed ZenHub to a "production landing zone" environment ✅
- Have successfully performed at least one [test migration](#testing-the-migration) to your "production landing zone" environment ✅

## Migration overview

The migration of your ZenHub data has 3 major steps.

1. **Gather** the data from your existing ZHE2 source instance.
2. **Move** the data to a jump box or workstation with network access to your new MongoDB, PostgreSQL, and bucket targets.
3. **Upload** the data to each target.

The steps below will outline how to make connections with the MongoDB and PostgreSQL databases, as well as the object storage bucket to migrate your data. Our examples demonstrate the migration process using a Macbook workstation. You might use a jumpbox or a different OS on your workstation, but the steps will be similar. Please reach out to ZenHub Support if you have any problems with the migration. These steps will assume that TLS has been enabled on your Postgres database already (TLS for MongoDB isn't supported yet), as is likely the case if you use a database-as-a-service provider.

## Testing the migration

To test the migration, we need to deploy ZHE3 without disturbing ZHE2. This is achieved by running the migration using a new GitHub OAuth App with a different domain configured. Then, when we've confirmed the migration was successful, we change the configuration to use the production OAuth and domain name.

### Choose a subdomain for the test
1. Select a test subdomain name for your migration. It could be zenhub-test.yourcompany.com, for example.
2. Configure this domain in your DNS manager to point to your Kubernetes ingress for ZenHub Enterprise.
3. Edit `subdomain_suffix` and `admin_ui_subdomain` in your `kustomization.yaml` to reflect your chosen test domain.
### Configure a temporary OAuth app
1. Follow the instructions [here](https://github.com/ZenHubHQ/zenhub-enterprise/tree/master/k8s-cluster#21-github-enterprise-server) to set up a new, temporary OAuth app. This will allow your application to authenticate to GitHub without disrupting the ZHE2 application.
2. Ensure you use your new subdomain in the Authorization callback URL.
3. Edit `github_app_id` and `github_app_secret` in your `kustomization.yaml` to reflect your temporary OAuth app.

### (Re)Deploy your application
```bash
kustomize build . | kubectl apply -f -
```
### Follow the Migration steps
Now that the DNS and OAuth app have been configured, you can proceed to the [Migration steps](#migration-steps) to complete the migration.

### Return to production config
Once you have successfully completed the test, return the values in your `kustomization.yaml` to your production configuration:
- `github_app_id`
- `github_app_secret`
- `subdomain_suffix`
- `admin_ui_subdomain`

You are now ready to migrate production. Schedule a maintenance window with your team and follow the [Migration steps](#migration-steps) to complete the migration.

## Migration steps
### Gather the data from your existing ZHE2 source instance

1. SSH to your existing ZHE2 source instance.
2. Download the `zhe3-migration-dump.sh` script from this folder to your existing ZHE2 instance.
3. Run the script (note: this will place the instance into maintenance mode for the duration, blocking user access to the application).

```bash
sudo ./zhe3-migration-dump.sh
```
>⚠️ **NOTE:** If you are testing the migration, you can disable maintenance mode after the script completes to resume service for users. Otherwise, if you are doing a production migration, leave maintenance mode enabled to prevent data loss during the migration.

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

### Upload the data to the DBs

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

2. Create a restorer user on the zenhub DB

Depending on the authentication and authorization system of your MongoDB provider, you may have to adjust these steps. In most systems, you will need to create a database user that has both `readWrite` and `dbAdmin` permissions to successfully restore the database.

```
mongo --username root --host zenhub-mongo.example.com --port 27017
```
> ⚠️ **NOTE:** You will be prompted for `--username`'s password.

```
use zenhub
db.createUser({user: "restorer", pwd: "the-restorer-password", roles: [ "readWrite", "dbAdmin" ]})
```
> ⚠️ **NOTE:** If you have already deployed ZenHub to your Kubernetes cluster and it has successfully connected to Mongo, the `zenhub` database should exist.

3. Expand the Mongo tarball

```bash
tar -xf mongo.tar.gz
```

4. Restore the Mongo database. The default name for the MongoDB database is `zenhub`, but if you have changed this (in your `mongo_url` connection string configured in your `kustomization.yaml` file), please reflect that in your restore command.

```bash
mongorestore --nsFrom='zenhub_enterprise.*' --nsTo='zenhub.*' --nsInclude='zenhub_enterprise.*' --stopOnError --noIndexRestore --drop --host zenhub-mongo.example.com --port 27017 --username restorer --authenticationDatabase=zenhub ./dump
```

> ⚠️ **NOTE:** Set the value of `authenticationDatabase` to whichever database you created your `restorer` user in from Step 3 above.

#### PostgreSQL

To restore the PostgreSQL dump we will need to have the PostgreSQL tools on your workstation/jumpbox. Install the latest PostgreSQL version 11 tools.

1. Install PostgreSQL tools

```bash
brew install postgresql@11
```

2. Download your PostgreSQL provider's CA certificate. For example, if you're using Amazon RDS, you can find it [here](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html).

3. Restore the DB. The default name for the PostgreSQL database is `raptor_production` and the default user is `postgres`, but if you have changed this (in your `postgres_url` connection string configured in your `kustomization.yaml` file), please reflect that in your restore command.

```bash
pg_restore --clean --no-owner -v -h zenhub.pg.example.com -p 5432 -d raptor_production -U postgres -W --sslrootcert=<path/to/postgres-ca-cert.pem> --sslmode=verify-full postgres_raptor_data.dump
```

### Update the references in the MongoDB blob collection

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

### Upload files and images to the object storage buckets
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
