# PgBouncer Configuration for Zenhub Enterprise

PgBouncer is an open-source, lightweight, single-binary connection pooler for PostgreSQL.
It helps PostgresSQL run at scale with a large number of client connections.

## Overview

If this is your first time setting up this pgbouncer configuration, please follow the instructions in: [Configuration for Postgres using scram-sha-256](#configuration-for-postgres-using-scram-sha-256).

If you are upgrading your postgres from a version that supports md5 authentication to a version that uses scram-sha-256 authentication, please follow the instructions in: [Configuration Upgrade from MD5 to SCRAM-SHA-256 Encryption](#configuration-upgrade-from-md5-to-scram-sha-256-encryption)

## Configuration for Postgres Using scram-sha-256

You will need to fill out and apply the userlist.txt and pgbouncer.ini files in order to configure PgBouncer. The instructions below will guide you through the process and show you how to setup the configuration files to work with scram-sha-256 authentication on your Postgres database.

### Prerequisites

- Be ready with your Postgres database user connection information.
- You are running Postgres version that uses password_encryption = scram-sha-256

### Configuring the userlist.txt file

This configuration file holds the username and passwords of the user(s) that have access to the PostgreSQL database to authenticate to the database as well as to connect to the internal 'pgbouncer' database that is used to manage PgBouncer once it is running.

The file will need to hold two users:

1) `my-pgbouncer-username` user, which is dedicated for PgBouncer -> Postgres communication
    - This is the same user that should be entered in **pgbouncer.ini** under the `[databases]` section
    - This password must be entered in plain-text in the file in order to use SCRAM authentication to Postgres [[reference](https://postgrespro.com/docs/postgrespro/9.6/pgbouncer#:~:text=To%20be%20able%20to%20use%20SCRAM%20on%20server%20connections%2C%20use%20plain%2Dtext%20passwords.)]
2) `my-postgres-username` user, which the Zenhub application stores and uses for Application -> PgBouncer or Postgres
    - This is the same user that should be used in `pgbouncer_url` and `postgres_url` in the main **kustomization.yaml** file
    - This password should be entered in SCRAM-SHA-256 format in the file

If you do not have access to the `pg_authid` table, you may use the provided scram.py script to generate the SCRAM-SHA-256 hash for your `my-postgres-username` user:

```bash
chmod 700 scram.py
./scram.py <my-postgres-password>
```

Once you have your SCRAM-SHA-256 hash, you may add it to the userlist.txt file. The resulting file should look similar to the following:

```txt
"<my-pgbouncer-username>" "plaintext"
"<my-postgres-username>" "SCRAM-SHA-256..."
```

If you do not already have a dedicated PgBouncer user yet to use as `my-pgbouncer-username`, please follow the instructions under [How to Create a Dedicated PgBouncer User](#how-to-create-a-dedicated-pgbouncer-user) just below:

#### How to Create a Dedicated PgBouncer User

Connect to your Postgres database as an administrative user and run the following commands:

> Set `my-pgbouncer-username` to the username of the new dedicated user to be created that manages PgBouncer to Postgres communication
>
> Set `my-pgbouncer-password` to the password to be created for the new user `my-pgbouncer-username`

```sql
--- Create the new `my-pgbouncer-username` user with a new password
SET password_encryption='scram-sha-256'; CREATE USER <my-pgbouncer-username> WITH PASSWORD '<my-pgbouncer-password>';

--- Grant permissions to `my-pgbouncer-username` user
GRANT CREATE ON SCHEMA public TO <my-pgbouncer-username>;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON tables TO <my-pgbouncer-username>;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public to "<my-pgbouncer-username>";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "<my-pgbouncer-username>";
```

### Configuring the pgbouncer.ini file

This configuration file holds the settings to be applied to PgBouncer. This includes TLS settings, database connection information, pooling configuration, etc.

Find and replace the following variables with values relevant to your deployment:

`my-db-name` - The name of the database used for Zenhub.

`my-postgres-host-name` - The hostname of the database.

`my-postgres-port` - The port of the database.

`my-pgbouncer-username` - The username of the dedicated user that is used for PgBouncer to Postgres communication.

`my-max-client-conn` - The maximum number of client connections that will need to concurrently access the database. Use your monthly active users as a reference.

`my-default-pool-size` - The size of the connection pool that will interact directly with Postgres. Set this to the number of available client PostgreSQL connections. Do not occupy all connections, as some connections may need to be left available for the database administrator. For example, if your PostgreSQL max_connections is 515, save 15 connections for administration by setting `my-default-pool-size` to `500`.

## How to Upgrade from MD5 to SCRAM-SHA-256 Encryption

Since Postgres Version 14, the default encryption method for authentication is SCRAM-SHA-256. PgBouncer will fail to communicate to the Postgres server unless the configuration is updated to match this restriction.
This section defines the steps for upgrading from the older, MD5 encryption standard to SCRAM-SHA-256.

1. First of all, you will need a dedicated PgBouncer user to handle communication from the PgBouncer to Postgres database. If you already have a dedicated user, please skip this step. Otherwise, please follow the instructions in [How to Create a Dedicated PgBouncer User](#how-to-create-a-dedicated-pgbouncer-user).

2. **Before upgrading** to Postgres Version 14+ (or any Postgres database that defaults to SCRAM-SHA-256), please make sure to re-hash the users that are used to connect to Postgres by following the instructions in [How to Rehash Passwords in SCRAM-SHA-256](#how-to-rehash-passwords-in-scram-sha-256).

The [pgbouncer] section of pgbouncer.ini has been modified in ZHE version 4.1 to set auth_type to `scram-sha-256` instead of `md5`, so if you are upgrading from a version that used md5, please ensure it is set to `scram-sha-256` in your pgbouncer.ini file.

### How to Rehash Passwords in SCRAM-SHA-256

The below instructions will trigger the re-hashing of passwords in SCRAM-SHA-256 format. You may use the same password for existing users.

Find and replace the following variables with values relevant to your deployment:

- `my-pgbouncer-username` - The username of the dedicated user to connect from PgBouncer to Postgres.
- `my-pgbouncer-password` - The password of the user `my-pgbouncer-username`. 
- `my-postgres-username` - The username of the user that is used to connect from the Zenhub application to PgBouncer or Postgres.
- `my-postgres-password` - The password of the user `my-postgres-username`.

Connect to your Postgres database as an administrative user and run the following commands:

```sql
--- Alter the `my-pgbouncer-username` user hash
SET password_encryption='scram-sha-256'; ALTER USER <my-pgbouncer-username> WITH PASSWORD '<my-pgbouncer-password>';

--- Verify the `my-pgbouncer-username` user hash
--- This may not work for some Postgres service providers due to restricted access to pg_shadow table.
SELECT passwd FROM pg_shadow WHERE usename = '<my-pgbouncer-password>';

--- Alter the "<my-postgres-username>" user hash
SET password_encryption='scram-sha-256'; ALTER USER postgres WITH PASSWORD '<postgres-password>';

--- Verfiy the "<my-postgres-username>" user hash
--- This may not work for some Postgres service providers due to restricted access to pg_shadow table.
SELECT passwd FROM pg_shadow WHERE usename = '<my-postgres-username>';
```

On a successful re-hash, the verification steps above should return a hash that starts with `SCRAM-SHA-256$4096`. If you do not have access to the `pg_shadow`, you will not be able to verify the hash.

Next, you will need to update the `userlist.txt` and `pgbouncer.ini` files with new configuration and the new passwords. For the `userlist.txt` file, you will need to update the `my-pgbouncer-username` password to the new plain-text password. For the `pgbouncer.ini` file, you will need to update the user in the `[databases]` section to the new dedicated `my-pgbouncer-username` user and update the `auth_type` to `scram-sha-256`. How to do this is described in the [Configuration for Postgres using scram-sha-256](#configuration-for-postgres-using-scram-sha-256) section.

Once the `userlist.txt` and `pgbouncer.ini` files are updated, you will need to update the pgbouncer K8S secrets and roll out the changes to the pgbouncer pod. To do this, follow the below steps:

1. Run the kustomize build process from the main directory to apply the changes to the pgbouncer K8S secrets.

    Check the diff to make sure the changes are as expected:

    ```bash
    kustomize build . | kubectl diff -f-
    ```

    If the diff looks good, apply the changes:

    ```bash
    kustomize build . | kubectl apply -f-
    ```

2. Restart the pgbouncer deployment so that it configures pgbouncer using the updated secrets.

    ```bash
    kubectl rollout restart deployment pgbouncer -n <zenhub-namespace>
    ```

## Usage

### How to Connect to the PgBouncer Admin Database

Once PgBouncer is deployed, you can connect to the 'pgbouncer' administration database via these steps:

1. Find the ClusterIP of the PgBouncer service and pod name for use later: `kubectl -n zenhub get svc,pod -l app.kubernetes.io/name=pgbouncer`
2. Exec into the PgBouncer pod: `kubectl -n <zenhub-namespace> exec -it <pgbouncer-pod-name> -- sh`
3. Run this command: `psql -p 5432 -U <username from admin_users list in pgbouncer.ini> --host <pgbouncer-cluster-ip> -d pgbouncer`
4. You're now connected! You can run commands like `show pools;`, or `show databases;`. Admin console command reference: https://www.pgbouncer.org/usage.html#admin-console