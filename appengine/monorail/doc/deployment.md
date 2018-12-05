# Monorail Deployment

## Deploying a new version to an existing instance

If any step below fails. Stop the deploy and ping [Monorail
chat](http://chat/room/AAAACV9ZZ8k).

1. Prequalify
    1. Check for signs of trouble
        1. [go/cit-hangout](http://go/cit-hangout)
        1. [Viceroy](http://go/monorail-prod-viceroy)
        1. [go/devx-pages](http://go/devx-pages)
        1. [GAE dashboard](https://console.cloud.google.com/appengine?project=monorail-prod&duration=PT1H)
        1. [Error Reporting](http://console.cloud.google.com/errors?time=P1D&order=COUNT_DESC&resolution=OPEN&resolution=ACKNOWLEDGED&project=monorail-prod)
    1. If there are any significant operational problems with Monorail or ChOps
       in general, halt deploy.
    1. `git pull`
    1. `gclient sync`
1. Update Schema
    1. Check for changes since last deploy: `tail -30 schema/alter-table-log.txt`
    1. Copy and paste the new changes into the master DB in staging.
       Please be careful when pasting into SQL prompt.
1. Upload Staging Version
    1. `make deploy_staging`
1. Test on Staging
    1. For each commit since last deploy, verify affected functionality still works.
1. Make Live on Staging
    1. Update module `besearch` to be the live version on staging.
    1. Update the other modules, `default` and `latency-insensitive`.
1. Upload Production Version
    1. `make deploy_prod`
    1. If you updated the staging schema, disconnect from the staging master DB so
       that command prompt is not left open in a terminal window.
1. On console.cloud.google.com, try out the new version using a version specific URL:
    1. Test some of the expected changes.
    1. Add a comment to an issue.
    1. Enter a new issue and CC your personal account.
    1. Verify that you got an email (at the "all" email address specified in settings.py).
    1. Try doing a query that is not cached, then repeat it to test the cached case.
1. Make Live on Prod
    1. Repeat the same schema changes on the prod database.
    1. Click on a bunch of projects to generate some traffic to the new version.
    1. Split traffic 1% with new version using cookie-based traffic splitting.
        1. **Important:** Make sure to split traffic for all 3 modules, starting
           with `besearch`.
    1. Wait an hour.
    1. If nothing looks off, proceed slowly to 25%, then 100%. Start with
       `besearch` each time.
    1. If you updated the prod schema, disconnect from the prod master DB so that
       command prompt is not left open in a terminal window.
1. Monitor Viceroy and Error Reporting
    1. Modest latency increases are normal in the first 10-20 minutes
    1. Check [/p/chromium updates page](https://bugs.chromium.org/p/chromium/updates/list).
    1. [Chromedash](http://go/chromedash), should work after deployment.
1. Announce the Deployment.
    1. Copy changes since last deploy: `git log --oneline .`
1. Add a new row to the [Monorail Deployment Stats](http://go/monorail-deployment-stats)
   spreadsheet to help track deploys/followups/rollbacks. It is important to do this
   even if the deploy failed for some reason.

## Creating and deploying a new Monorail instance

1.  Create new GAE apps for production and staging.
1.  Configure GCP billing.
1.  Create new master DBs and 10 read replicas for prod and staging.
    1.  Set up IP address and configure admin password and allowed IP addr. [Instructions](https://cloud.google.com/sql/docs/mysql-client#configure-instance-mysql).
    1.  Set up backups on master.  The first backup must be created before you can configure replicas.
1.  Fork settings.py and configure every part of it, especially trusted domains and "all" email settings.
1.  You might want to also update `*/*_constants.py` files.
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
