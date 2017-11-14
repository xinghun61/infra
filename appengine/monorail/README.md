# Monorail Issue Tracker

Monorail is the Issue Tracker used by the Chromium project and other related
projects. It is hosted at [bugs.chromium.org](https://bugs.chromium.org).

If you wish to file a bug against Monorail itself, please do so in our
[self-hosting tracker](https://bugs.chromium.org/p/monorail/issues/entry).
We also discuss development of Monorail at `infra-dev@chromium.org`.


# Getting started with Monorail development

Here's how to run Monorail locally for development on any unix system (not under google3):



1.  You need to [get the Chrome Infra depot_tools commands](https://commondatastorage.googleapis.com/chrome-infra-docs/flat/depot_tools/docs/html/depot_tools_tutorial.html#_setting_up) to check out the source code and all its related dependencies and to be able to send changes for review.
1.  Check out the Monorail source code
    1.  `cd /path/to/empty/workdir`
    1.  `fetch infra`
    1.  `cd infra/appengine/monorail`
1.  Make sure you have the AppEngine SDK:
    1.  It should be fetched for you by step 1 above (during runhooks)
    1.  Otherwise, you can download it from https://developers.google.com/appengine/downloads#Google_App_Engine_SDK_for_Python
1.  [Install MySQL v5.6](http://dev.mysql.com/downloads/mysql/5.6.html#downloads). Either download directly, or if you're on an Ubuntu derivative:
    1.  **Do not download v5.7 (as of April 2016)**
    1.  `sudo apt-get install mysql-server mysql-client`
1.  Get the database backend running and use the command-line to create a database named "monorail":
    1.  `sudo /usr/local/mysql/bin/mysqld_safe `
    1.  `mysql --user=root --password=<pw>`
    1.  `CREATE DATABASE monorail;`
1.  Install Python MySQLdb. Either:
    1.  `sudo apt-get install python-mysqldb`
    1.  Or, download from http://sourceforge.net/projects/mysql-python/
        1.  Follow instructions to install.
        1.  If needed, add these lines to your ~/.profile file and restart on MacOS 10.8:
            1.  setenv DYLD_LIBRARY_PATH /usr/local/mysql/lib/
            1.  setenv VERSIONER_PYTHON_PREFER_64_BIT no
            1.  setenv VERSIONER_PYTHON_PREFER_32_BIT yes
        1.  In Mac OSX 10.11.1, if you see errors about failing to import MySQLdb or that _mysql.so references an untrusted relative path, then run:
  sudo install_name_tool -change libmysqlclient.18.dylib \
  /usr/local/mysql/lib/libmysqlclient.18.dylib \
  /Library/Python/2.7/site-packages/_mysql.so
1.  Set up one master SQL database. (You can keep the same sharding options in settings.py that you have configured for production.).
    1.  `mysql --user=root monorail < schema/framework.sql`
    1.  `mysql --user=root monorail < schema/project.sql`
    1.  `mysql --user=root monorail < schema/tracker.sql`
1.  Configure the site defaults in settings.py.  You can leave it as-is for now.
1.  Run the app:
    1.  You can use 'make serve', or
    1.  Run the app with AppEngine dev_appserver.py with the command: `../../../google_appengine/dev_appserver.py --mysql_user=root app.yaml module-besearch.yaml`
1.  Browse the app at localhost:8080 your browser.
1.  Optional: Create/modify your Monorail User row in the database and make that user a site admin. 
    1.  `UPDATE User SET is_site_admin = TRUE WHERE email = 'YOUR@EMAIL';`
    1.  `Restart your local dev appserver.`

Here's how to run unit tests from the command-line:



1.  `cd infra`
1.  `./test.py test appengine/monorail`
1.  Or, in the monorail directory, use `'make test'`

Here's how to deploy a new version to an instance that has already been set up:



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

Here's an outline of what would be needed to set up a new Monorail instance:



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


## Troubleshooting



*   **<code>TypeError: connect() got an unexpected keyword argument 'charset'</code></strong>
This error occurs when dev_appserver cannot find the MySQLdb library.  Try installing it via <code>sudo apt-get install python-mysqldb</code>.
*   <strong><code>TypeError: connect() argument 6 must be string, not None</code></strong>
This occurs when your mysql server is not running.  Check if it is running with ps aux | grep mysqld.  Start it up with <code>/etc/init.d/mysqld start </code>on linux, or just <code>mysqld</code>.
*   dev_appserver says <strong><code>OSError: [Errno 24] Too many open files </code></strong>and then lists out all source files
dev_appserver wants to reload source files that you have changed in the editor, however that feature does not seem to work well with multiple GAE modules and instances running in different processes.  The workaround is to control-C or <strong><code>kill</code></strong> the dev_appserver processes and restart them.
