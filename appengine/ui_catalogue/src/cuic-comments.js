// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

class Comments extends ElementBaseWithUrls {

  static get is() {return 'cuic-comments';}

  static get properties() {
    return {
      comments_: Array,
      commentText_: String,
      key: String,
    };
  }

  handleGetResponse_(e) {
    this.set('comments_', e.detail.response);
  }

  handleGetError_(e) {
    alert('Error getting comments')
    console.log('Error getting comments');
    console.log(e.detail);
  }

  addComment_(e) {
    this.$['post-comment'].generateRequest();
  }

  handlePostResponse_(e) {
    // Update comments
    this.fetchComments_();
    // Clear new comment text
    this.set('commentText_', '');
  }

  computeCommentListUrl_(key) {
    // If the key is empty or null, clear the URL so that iron-ajax doesn't
    // make the request.
    if (!key) return '';
    return '/service/' + key + '/comments';
  }

  handlePostError_(e) {
    alert('Error posting comment')
    console.log('Error posting comment');
    console.log(e.detail);
    // Update displayed comments
    this.fetchComments_();
  }

  handleCommentsChanged_(e) {
    this.fetchComments_()
  }

  fetchComments_() {
    this.$['get-comments'].generateRequest();
  }
}

window.customElements.define(Comments.is, Comments);
