# Monorail Deployment

## Deploying a new version to an existing instance

1.  You need the master and replica databases set up on the Developer API console
1.  Make sure that the app ID is correct in app.yaml.
1.  In the monorail directory, run the command  `make deploy_staging `
1.  Make any needed schema changes by looking at the end of sql/alter-table-log.txt.  Be sure to connect to the staging master DB.
1.  On console.cloud.google.com, try out the new version using a version specific URL:
    1.  Test some of the expected changes
    1.  Add a comment to an issue
    1.  Enter a new issue and CC your personal account
    1.  Verify that you got an email (at the "all" email address specified in settings.py)
    1.  Try doing a query that is not cached, then repeat it to test the cached case
1.  When everything looks good, make the new version the default on staging.
1.  If you updated the staging schema, disconnect from the staging master DB so that command prompt is not left open in a terminal window.
1.  Repeat the process on prod.  Be sure to repeat the same schema changes on the prod database.
1.  If you updated the prod schema, disconnect from the prod master DB so that command prompt is not left open in a terminal window.

## Creating and deploying a new Monorail instance

1.  Create new GAE apps for production and staging.
1.  Configure GCP billing.
1.  Create new master DBs and 10 read replicas for prod and staging.
    1.  Set up IP address and configure admin password and allowed IP addr. [Instructions](https://cloud.google.com/sql/docs/mysql-client#configure-instance-mysql).
    1.  Set up backups on master.  The first backup must be created before you can configure replicas.
1.  Fork settings.py and configure every part of it, especially trusted domains and "all" email settings.
1.  You might want to also update */*_constants.py files.
1.  Set up log saving to bigquery or something.
1.  Set up monitoring and alerts.
1.  Set up attachment storage in GCS.
1.  Set up spam data and train models.
1.  Fork and customize some of HTML in templates/framework/master-header.ezt, master-footer.ezt, and some CSS to give the instance a visually different appearance.
1.  Get From-address whitelisted so that the "View issue" link in Gmail/Inbox works.
1.  Set up a custom domain with SSL and get that configured into GAE.  Make sure to have some kind of reminder system set up so that you know before cert expire.
1.  Configure the API.  Details?  Allowed clients are now configured through luci-config, so that is a whole other thing to set up.  (Or, maybe decide not to offer any API access.)
1.  Gain permission to sync GGG user groups.  Set up borgcron job to sync user groups. Configure that job to hit the API for your instance.  (Or, maybe decide not to sync any user groups.)
1.  Monorail does not not access any internal APIs, so no whitelisting is required.
1.  For projects on code.google.com, coordinate with that team to set flags to do per-issue redirects from old project to new site.  As each project is imported, set it's moved-to field.
