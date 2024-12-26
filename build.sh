#!/bin/bash

# Install system dependencies for matplotlib
apt-get update
apt-get install -y python3-dev python3-pip python3-setuptools
apt-get install -y libfreetype6-dev pkg-config

# Create directories and copy files
mkdir -p dist
cp -r templates/* dist/
cp -r static dist/
