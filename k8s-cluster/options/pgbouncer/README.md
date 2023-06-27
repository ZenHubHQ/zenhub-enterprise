# PGBouncer Configuration

PGBouncer is an open-source, lightweight, single-binary connection pooler for PostgreSQL.
It helps PostgresSQL run at scale with a large number of client connections.

## Prerequisites

- Be ready with your Postgres database user connection information.

## How to Configure

### userlist.txt

This configuration file holds the username and md5 hashed password+username combinations of the user(s) that have access to the PostgreSQL database to authenticate to the database as well as to connect to the internal 'pgbouncer' database that is used to manage PgBouncer once it is running.

The file should look similar to the following when filled out:

```bash
"zenhub" "md5asdasd"
```

The example above is for a Postgres user with the name 'zenhub'.

Here are 3 ways you can create the md5 hash, where the username is 'zenhub' and the password is 'password123' as an example:

#### Linux

```bash
echo -n "md5"; echo -n "password123zenhub" | md5sum | awk '{print $1}'
```

#### MacOS

```bash
echo -n "md5"; md5 -qs "password123zenhub"
```

#### Python 3

```python
import hashlib
print("md5" + hashlib.md5("password123" + "zenhub").hexdigest())
```

### pgbouncer.ini

This configuration file holds the settings to be applied to PgBouncer. This includes TLS settings, database connection information, pooling configuration, etc.

Find and replace the following variables with values relevant to your deployment:

`my-db-name` - The name of the database used for Zenhub.

`my-postgres-host-name` - The hostname of the database.

`my-postgres-port` - The port of the database.

`my-postgres-username` - The username of the user for connecting to the Postgres database and internal PgBouncer management database. Replace both occurrences.

`my-max-client-conn` - The maximum number of client connections that will need to concurrently access the database. Use your monthly active users as a reference.

`my-default-pool-size` - The size of the connection pool that will interact directly with Postgres. Set this to the number of available client PostgresSQL connections. Do not occupy all connections, as some connections may need to be left available for database administrator. For example, if your PostgresSQL max_connections is 515, save 15 connections for administration by setting `my-default-pool-size` to `500`.

## How to Connect

Once PgBouncer is deployed, you can connect to the 'pgbouncer' administration database via these steps:

1. Find the ClusterIP of the pgbouncer service and podname for use later: `kubectl -n zenhub get svc,pod -l app.kubernetes.io/name=pgbouncer`
2. Exec into the pgbouncer pod: `kubectl -n zenhub exec -it <pgbouncer-pod-name> -- sh`
3. Run this command: `psql -p 5432 -U <username from admin_users list in pgbouncer.ini> --host <pgbouncer-cluster-ip> -d pgbouncer`
4. You're now connected! You can run commands like `show pools;`, or `show databases;`. Admin console command reference: https://www.pgbouncer.org/usage.html#admin-console