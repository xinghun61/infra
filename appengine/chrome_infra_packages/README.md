# CIPD backend and Web UI

TODO: describe what is CIPD.

## Development

To hack on the app locally:

    # Remove vulcanized version of index to switch to non-vulcanized one.
    make clean
    # Launch devserver, visit http://localhost:8080.
    ./tools/gae devserver
    # hack-hack-hack
    ...
    # Run python unit tests.
    ./tools/run_tests.sh

To deploy the application:

    # Install node.js & vulcanize.
    make setup
    # Vulcanize the index page.
    make build
    # Make sure it looks fine locally, visit http://localhost:8080
    ./tools/gae devserver
    # Deploy to staging (as default version).
    ./tools/gae upload -x
    # Deploy to prod as non-default version.
    ./tools/gae upload -A chrome-infra-packages
    # Make it default.
    ./tools/gae switch -A chrome-infra-packages


## Using Google Storage on dev server backend

If you want to try changes end-to-end locally you'd need to configure local
app with service account credentials and Google Storage bucket paths (writable
by the service account).

To do so:

1.  Create a new service account in some Cloud Project (or use some existing
    one). Download its JSON keys file.
1.  Grant this service account access to some Google Storage bucket.
1.  Launch devserver.
1.  Register yourself as an admin by going to
    http://localhost:8080/auth/bootstrap and signing in with your real email.
    Check "Sign in as Administrator" box.
1.  Wait 30 sec.
1.  Go to http://localhost:8080/_ah/api/explorer.
1.  Navigate to Services > CIPD Administration API v1 > admin.setServiceAccount.
1.  Toggle "Authorize requests using OAuth 2.0" to On, sign in with the same
    email as in step 4.
1.  Paste service account JSON key into the "Request body" field, make the call.
1.  Navigate to Services > CIPD Administration API v1 >
    admin.setGoogleStorageConfig.
1.  Specify Google Storage paths where to store uploaded files and temporary
    stuff, for example:

    ```json
    {
      "cas_gs_path": "/playground-bucket/dev/store",
      "cas_gs_temp": "/playground-bucket/dev/temp"
    }
    ```

1.  Upload something using CIPD client to verify everything works:

    ```
    ./cipd auth-login
    ./cipd create -in=<path> -name=local/test -service-url=http://localhost:8080
    ```
