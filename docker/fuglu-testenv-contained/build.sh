#!/bin/bash

imagename=fuglu_img

if [ -z "$1" ]; then
   echo "********************************************************************"
   echo "new build for image $imagename: use cache"
   echo "********************************************************************"
   docker build -t $imagename -f Dockerfile ../../.
else
   echo "===================================================================="
   echo "new build for image $imagename: pull image and don't use cache"
   echo "===================================================================="
   docker build -t $imagename --no-cache --pull -f Dockerfile ../../fuglu/.
fi

