# Dockerfile extending the generic Python image with application files for a
# single application.
FROM google/appengine-python27

# Install dev tools to compile C-accelerated python modules.
RUN apt-get -y update
RUN apt-get -y upgrade
RUN apt-get -y install build-essential
RUN apt-get -y install python-dev

# Required by pyopenssl.
RUN apt-get -y install libffi-dev
RUN pip install --upgrade setuptools

# Required by oauth2client.client.SignedJwtAssertionCredentials.
RUN pip install --upgrade pyopenssl

RUN pip install --upgrade google-api-python-client
