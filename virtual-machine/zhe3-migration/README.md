# ZHE2 to ZHE3 Migration for Virtual Machine

> ⚠️ **NOTE:** This page is only applicable to users of the previous-generation ZenHub Enterprise 2.x. **Migrations from 2.x are only supported on ZenHub Enterprise 3.1.x**.

## Table of Contents
- [When am I ready to migrate production?](#when-am-i-ready-to-migrate-production)
- [Migration overview](#migration-overview)
- [Gather the data from your existing ZHE2 source instance](#gather-the-data-from-your-existing-zhe2-source-instance)
- [Move the data to your virtual machine](#move-the-data-to-your-virtual-machine)
- [Restore the data](#restore-the-data)

### When am I ready to migrate production?

By its nature, the migration of ZenHub to the new ZHE3 infrastructure is a complex process. For this reason, it is important to validate the migration as much as possible before migrating your production ZenHub deployment to minimize downtime for users and decrease the probability of issues occurring.

Before planning a production migration, we recommend that customers have achieved the following milestones:
- Have successfully deployed ZenHub to a "production landing zone" environment ✅
- Have successfully performed at least one full data migration to your "production landing zone" environment ✅

In this case, the landing zone will be the ZHE3 virtual machine. To test the migration without impacting production, you can use a different DNS record for the ZHE3 virtual machine while your ZHE2 instance is still serving users. You can simply set up another OAuth App on your GitHub Enterprise temporarily and configure your VM to use the given OAuth App ID and secret.

<!-- TODO: A section on no-downtime testing of migration -->

### Migration overview

> ⚠️ **NOTE:** Before migrating data, you must have ZenHub Enterprise 3 already setup and operational. Checkout the [ZHE3 for VM deployment documentation](https://github.com/ZenHubHQ/zenhub-enterprise/blob/master/virtual-machine/README.md) for detailed steps on how to get ZenHub Enterprise 3 up and running.

The migration of your ZenHub data has 3 major steps.

1. **Gather** the data from your existing ZHE2 source instance.
2. **Move** the data to your new virtual machine.
3. **Restore** the data to your new virtual machine.

Please reach out to ZenHub Support if you have any problems with the migration.

### Gather the data from your existing ZHE2 source instance

1. SSH to your existing ZHE2 source instance.
2. Download the `zhe3-migration-dump.sh` script from [here](https://github.com/ZenHubHQ/zenhub-enterprise/blob/master/k8s-cluster/zhe3-migration/zhe3-migration-dump.sh) to your _existing_ ZHE2 instance.
3. Run the script (note: this will dump the databases which may impact performance for the duration).

```bash
sudo ./zhe3-migration-dump.sh
```

### Move the data to your virtual machine

1. SSH to your new ZHE3 instance.
2. Make a directory for your migration data to be uploaded to:
```bash
sudo mkdir /opt/import
```

3. Using `scp` or your chosen tool, move your `migration-data-<timestamp>.tar.gz` bundle to the directory `/opt/import` on the new VM that has ZenHub Enterprise already configured and running.
> The resulting path to the data being migrated will be `/opt/import/migration-data-<timestamp>.tar.gz`

### Restore the data

1. Run the migration tool via the command below. Replace the timestamp with that of your own backup bundle's
```
zhe-config --zhe2-migrate migration-data-<timestamp>.tar.gz
```

2. Wait for the migration to complete.

Congrats! 🎉 All of your data should now be migrated and ready to use in ZHE3.
