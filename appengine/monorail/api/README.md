# Monorail API v2

This directory holds all the source for the Monorail API v2. This API is
implemented using `.proto` files to describe a `gRPC` interface (services,
methods, and request/response messages). It then uses a shim which
converts the
[`gRPC` server](http://www.grpc.io/docs/tutorials/basic/python.html)
(which doesn't work on AppEngine, due to lack of support for HTTP/2) into a
[`pRPC` server](https://godoc.org/github.com/luci/luci-go/grpc/prpc) which
supports communication over HTTP/1.1, as well as text and JSON IO.

## Regenerating Python from Protocol Buffers

In order to regenerate the python server and client stubs from the `.proto`
files, run this command:

```bash
$ make prpc_proto
```


## Manually Exercising the API

You can make anonymous requests to a server running locally like this:

```bash
$ curl -i -X POST localhost:8080/prpc/monorail.Users/GetUser \
  -H "Content-Type: application/json" -H "Accept: application/json" \
  --data '{"email": "test@example.com"}'
```

Requests that require a signed-in user can be tested locally like this
(done with an alias so that the command is shorter):

```bash
$ alias capi-dc='curl -i -X POST localhost:8080/prpc/monorail.Issues/DeleteComment -H "Content-Type: application/json" -H "Accept: application/json"'
$ capi-dc --data '{"trace": {"test_account": "test@example.com"}, "issue_ref": {"project_name": "proj", "local_id": 21}, "sequence_num": 1}'
```
