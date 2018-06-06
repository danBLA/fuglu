#!/bin/bash

display_help(){
   echo ""
   echo "----------------------------------#"
   echo "- Local gitlab testing framework -#"
   echo "----------------------------------#"
   echo ""
   echo " Hosting this repo on gitlab automatic testing can be defined .gitlab-ci.yml"
   echo " in the main directory. It is also possible to run these test locally (which"
   echo " I would recommend before submitting)."
   echo ""
   echo " This scripts runs all the tests which will also run on gitlab. Plesae not"
   echo " changes have to be commited to be tested."
   echo ""
   echo " Requirements:"
   echo " 1) docker repo on local host running containing fuglu testing image"
   echo "     - install docker"
   echo "     - create local registry (https://docs.docker.com/registry/deploying/#run-a-local-registry)"
   echo "       (docker run -d -p 5000:5000 --restart=always --name registry registry:2)"
   echo "     - cd to fuglu/develop/docker/centos-7"
   echo "     - build a container running "buildTagPush.sh". This container is used for"
   echo "       the testing by titlab-runner"
   echo " 2) install gitlab-runner (https://docs.gitlab.com/runner/install/linux-repository.html)"
   echo ""
}

# no arguments needed, print help if there are any...
if [ $# -ne 0 ]; then
   display_help
   exit 0
fi

maindir=$(cd "$(dirname "$0")/../../"; pwd)

echo "maindir: $maindir"
cd $maindir

alljobs=(buildfuglu_py3 buildfuglu unittests_py3 unittests integrationtests_py3 integrationtests)

for job in "${alljobs[@]}"
do
   echo ""
   echo ""
   echo "--------------------------------"
   echo "Running job $job"
   echo "--------------------------------"
   echo ""
   gitlab-runner exec docker $job
   # check return
   rc=$?; if [[ $rc != 0 ]]; then exit $rc; fi
done

cd -
exit 0