#!/bin/bash

wait_for_port() {
   if [ -z "$1" ];  then
      echo "wait_for_port: 1st argument (server) is missing!"
      exit 1
   fi

   if [ -z "$2" ];  then
      echo "wait_for_port: 2nd argument (port) is missing!"
      exit 1
   fi

   if [ -z "$3" ];  then
      echo "wait_for_file: 3nd argument (maxtries) is missing!"
      exit 1
   fi

   if [ -z "$4" ];  then
      echo "wait_for_file: 3nd argument (sleeptime) is missing!"
      exit 1
   fi

   echo "------------------------------------------"
   echo "- Wait for port $2 to be open on host $1 -"
   echo "------------------------------------------"

   counter=0
   maxcounter=$3
   while ! [ `nmap -sT $1 -p $2 | grep -c open` -gt 0 ] && [ $counter -lt $maxcounter ] ; do
      echo "waiting... $4 secs [$counter/$maxcounter]"
      let counter=counter+1
      sleep $4
   done
   if ! [ $counter -lt $maxcounter ]; then
      echo "time limit reached!"
      nmap -sT $1 -p $2
      exit 1
   fi
   echo "Success, port is open"
}

wait_for_port spamd 783 2700 1
wait_for_port clamd 3310 2700 1
