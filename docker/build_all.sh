#!/bin/bash

set -e
set -x

base=$PWD
for p in clamd fuglu-testenv-contained spamd; do
   if [ -e $PWD/$p/build.sh ]; then
      echo "Build $p from build script"
      cd $base/$p && $SHELL ./build.sh
   elif [ -e $base/$p/Dockerfile ]; then
      imname="fuglu_img_$p"
      echo "Build $p from Dockerfile to image $imname"
      docker build -t $imname -f $base/$p/Dockerfile  $base/../.
   else
      echo "Could not fine a way to build the docker image for $p"
   fi
done
