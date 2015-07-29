This app proxies connections from external clients to the internal
monitoring endpoint for timeseries data.

The clients push data directly to PubSub using the ts_mon library, and
a thin Go client running on a GCE VM with a static (whitelisted) IP
polls the subscription and forwards data to the final endpoint.

Build the docker container
---------------------------

```
  cd infra/go
  ./env.py go build infra/monitoring/proxy
  cp proxy ../docker/monitoring_proxy
  cd ../docker/monitoring_proxy
  ./docker_build.sh dev
```

The `docker_build.sh` script generates
`monitoring_proxy_containers_dev.yaml` with the correct docker image
tag, which is used by the `setup.sh` script.

Testing on a staging instance
-----------------------------

Cloud project: chrome-infra-mon-proxy-dev

The app reads its parameters from the [Metadata
server](https://pantheon.corp.google.com/project/chrome-infra-mon-proxy-dev/compute/metadata) on startup;
make sure parameters are set as you expect.

If you change Metadata parameters, you need to restart the app either
by respinning the VM (`./setup.sh proxy[1-3] dev`), or ssh to the VM
and kill the docker container (`sudo docker kill <container hash>`).
Kubelet will restart the container in a few seconds.

* `monitoring_proxy_endpoint_url`: where to send the data. For staging
   instance, it is typically a loadtest endpoint.
* `monitoring_proxy_endpoint_auth_json`: service account credentials
  in JSON format for the endpoint.
* `monitoring_proxy_log_level`: keep it `info` for production
  instance, and `debug` for staging, unless you plan a heavy loadtest.
* `monitoring_proxy_pubsub_batch_size`: 100 is a good number.
* `monitoring_proxy_pubsub_project`: `chrome-infra-mon-pubsub`
* `monitoring_proxy_pubsub_subscription`: staging - `test-sub`,
  production - `monacq-proxy`.
* `monitoring_proxy_workers`: 50 is a good number for heavy loads.

The app's default Compute Engine service account should be added to
the PubSub Cloud project (under `APIs & auth` / `Credentials` tab).

Deploy the container on a staging instance:

```
  ./setup.sh proxy1 dev
  ./setup.sh proxy2 dev
  ./setup.sh proxy3 dev
```

Run loadtest through the dev instance using
https://chrome-infra-loadtest.appspot.com by pointing it to
`pubsub://chrome-infra-mon-pubsub/test` and providing credentials
recognized by `chrome-infra-pubsub` Cloud project.

Deploying to production instance
--------------------------------

Cloud project: chrome-infra-mon-proxy

If everything looks good, you are ready to commit and deploy the app
in production.

```
  ./docker_build.sh prod
```

Commit your change with the newly generated
`monitoring_proxy_containers_{dev,prod}.yaml` in a separate CL
(important for later reverts!), and deploy the new containers:

```
  ./setup.sh proxy1 prod
  ./setup.sh proxy2 prod
  ./setup.sh proxy3 prod
```

Revert the previously deployed change
-------------------------------------

Revert the relevant CL, or update the image hash in
`monitoring_proxy_go_containers.yaml` to a known good version, and
run

```
  ./setup.sh proxy1 prod
  ./setup.sh proxy2 prod
  ./setup.sh proxy3 prod
```

Note, that there is no easy way to list uploaded docker containers in
a Cloud project. Therefore, we store image tags in infra.git repo.
