// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import '@chopsui/prpc-client';

const PrpcClient = window.chops.rpc.PrpcClient;

suite('PrpcClient.constructor', () => {

  test('constructor defaults', () => {
    const client = new PrpcClient();
    assert.equal(client.host, document.location.host);
    assert.equal(client.accessToken, null);
    assert.equal(client.insecure, false);
  });
});

suite('PrpcClient.call', () => {
  let client, fetchStub, message, response;
  setup(() => {
    client = new PrpcClient();
    response = new Response(')]}\'{"rutabaga": "response"}');
    response.headers.set('X-Prpc-Grpc-Code', '0');
    fetchStub = sinon.stub().returns(Promise.resolve(response));
    message = { rutabaga: 'request' };
  });

  test('required args', async () => {
    try {
      await client.call(null, 'method', {});
      assert.fail(true, 'this line should never be reached');
    } catch (err) {
      assert.include(err.message, 'missing required argument: service');
    }
    try {
      await client.call('service', null, {});
      assert.fail(true, 'this line should never be reached');
    } catch (err) {
      assert.include(err.message, 'missing required argument: method');
    }
    try {
      await client.call('service', 'method');
      assert.fail(true, 'this line should never be reached');
    } catch (err) {
      assert.include(err.message, 'missing required argument: message');
    }
  });

  test('message must be an object', async () => {
    try {
      await client.call('service', 'method', 'rutabaga');
      assert.fail(true, 'this line should never be reached');
    } catch (err) {
      assert.include(err.message, 'must be a protobuf object');
    }
  });

  test('happy path', async () => {
    client = new PrpcClient({
      host: 'host',
      accessToken: 'access-token',
      insecure: false,
      fetchImpl: fetchStub,
    });
    const resMessage = await client.call('service', 'method', message);
    sinon.assert.calledWith(fetchStub,
        'https://host/prpc/service/method', {
          credentials: 'omit',
          method: 'POST',
          headers: {
            accept: 'application/json',
            authorization: 'Bearer access-token',
            'content-type': 'application/json',
          },
          body: '{"rutabaga":"request"}',
        });
    assert.deepEqual(resMessage, {rutabaga: 'response'});
  });

  test('gRPC non-OK message', async () => {
    response = new Response('an error message');
    response.headers.set('X-Prpc-Grpc-Code', '5');
    fetchStub = sinon.stub().returns(Promise.resolve(response));
    client = new PrpcClient({
      host: 'host',
      accessToken: 'access-token',
      fetchImpl: fetchStub,
    });
    try {
      await client.call('service', 'method', message);
      assert.fail(true, 'this line should never be reached');
    } catch (err) {
      sinon.assert.calledWith(fetchStub,
          'https://host/prpc/service/method', {
            method: 'POST',
            credentials: 'omit',
            headers: {
              'accept': 'application/json',
              'content-type': 'application/json',
              'authorization': 'Bearer access-token',
            },
            body: '{"rutabaga":"request"}',
          });
      assert.instanceOf(err, window.chops.rpc.GrpcError);
      assert.equal(err.code, 5);
      assert.equal(err.codeName, 'NOT_FOUND');
      assert.equal(err.description, 'an error message');
      assert.equal(err.message, 'code: 5 (NOT_FOUND) desc: an error message');
    }
  });

  test('NaN gRPC code', async () => {
    client = new PrpcClient({
      host: 'host',
      accessToken: 'access-token',
      fetchImpl: fetchStub,
    });
    response.headers.set('X-Prpc-Grpc-Code', 'rutabaga');
    try {
      await client.call('service', 'method', message);
      assert.fail(true, 'this line should never be reached');
    } catch (err) {
      sinon.assert.calledWith(fetchStub,
          'https://host/prpc/service/method', {
            method: 'POST',
            credentials: 'omit',
            headers: {
              'accept': 'application/json',
              'content-type': 'application/json',
              'authorization': 'Bearer access-token',
            },
            body: '{"rutabaga":"request"}',
          });
      assert.instanceOf(err, window.chops.rpc.ProtocolError);
      assert.equal(err.httpStatus, 200);
      assert.equal(err.description, 'Invalid X-Prpc-Grpc-Code response header');
    }
  });

  test('BYOfetch', async () => {
    const ourFetch = async (url, options) => {
      const response = new Response(')]}\'{"rutabaga": "rutabaga"}');
      response.headers.set('X-Prpc-Grpc-Code', '0');
      return response;
    };
    client = new PrpcClient({
      host: 'host',
      accessToken: 'access-token',
      fetchImpl: ourFetch,
    });
    const resMessage = await client.call('service', 'method', message);
    sinon.assert.callCount(fetchStub, 0);
    assert.deepEqual(resMessage, {rutabaga: 'rutabaga'});
  });
});

suite('GrpcError', () => {
  test('constructor', () => {
    const error = new window.chops.rpc.GrpcError(13, 'description');
    assert.equal(error.code, 13);
    assert.equal(error.description, 'description');
    assert.equal(error.message, 'code: 13 (INTERNAL) desc: description');
  });
});

suite('ProtocolError', () => {
  test('constructor', () => {
    const error = new window.chops.rpc.ProtocolError(400, 'description');
    assert.equal(error.httpStatus, 400);
    assert.equal(error.description, 'description');
    assert.equal(error.message, 'status: 400 desc: description');
  });
});
