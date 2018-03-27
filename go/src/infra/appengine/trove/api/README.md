May sure you have env set up properly for flex, e.g.:

```
GOOGLE_APPLICATION_CREDENTIALS=/usr/local/google/home/$USER/Downloads/test-trove-<some id>.json
GOOGLE_CLOUD_PROJECT=test-trove
GCLOUD_PROJECT=test-trove
GAE_SERVICE=default
GAE_VERSION=default
```

To start the server:

```
go run main.go
```

