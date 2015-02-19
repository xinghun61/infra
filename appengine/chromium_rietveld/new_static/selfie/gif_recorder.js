// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function GifRecorder(options)
{
    this.webcam = options.webcam;
    this.width = Math.round(options.width || 0);
    this.height = Math.round(options.height || 0);
    this.quality = options.quality || 10;
    this.workers = options.workers || 2;
    this.maxFrames = options.maxFrames || 14;
    this.delay = options.delay || 150;
    this.remainingFrames = 0;
    this.encoder = null;

    var canvas = document.createElement("canvas");
    canvas.width = this.width;
    canvas.height = this.height;
    this.context = canvas.getContext("2d");
}

GifRecorder.WORKER_URL = "new_static/bower_components/gif.js/dist/gif.worker.js";

GifRecorder.prototype.ensureEncoder = function()
{
    if (this.encoder)
        return;
    this.encoder = new GIF({
        workers: this.workers,
        workerScript: GifRecorder.WORKER_URL,
        width: this.width,
        height: this.height,
        quality: this.quality,
    });
};

GifRecorder.prototype.captureNextFrame = function()
{
    this.webcam.captureFrame(this.context, this.width, this.height);
    this.encoder.addFrame(this.context, {delay: this.delay, copy:true});
    return --this.remainingFrames;
};

GifRecorder.prototype.captureFrames = function()
{
    var self = this;
    return new Promise(function(resolve, reject) {
        self.remainingFrames = self.maxFrames;
        function nextFrame() {
            try {
                if (self.captureNextFrame())
                    setTimeout(nextFrame, self.delay);
                else
                    resolve();
            } catch (e) {
                reject(e);
            }
        }
        nextFrame();
    });
};

GifRecorder.prototype.renderFrames = function()
{
    var self = this;
    return new Promise(function(resolve, reject) {
        self.encoder.render();
        self.encoder.on("finished", function(blob) {
            try {
                self.encoder.abort();
                resolve(blob);
            } catch (e) {
                reject(e);
            }
        });
    });
};

GifRecorder.prototype.encodeImageData = function(blob)
{
    return new Promise(function(resolve, reject) {
        var reader = new FileReader();
        reader.readAsDataURL(blob);
        reader.onloadend = function() {
            resolve(reader.result);
        };
    });
};

GifRecorder.prototype.record = function()
{
    this.ensureEncoder();
    return this.captureFrames()
        .then(this.renderFrames.bind(this))
        .then(this.encodeImageData.bind(this));
};
