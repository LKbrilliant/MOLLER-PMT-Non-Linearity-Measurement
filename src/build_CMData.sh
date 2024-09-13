#!/bin/bash
# Build the CMData from source
# https://github.com/mtgericke/MOLLER-IntElec-ProtoSoft/tree/rev1
# commit: 6c61c4d
DIR=$1
mkdir -p $DIR/lib/build
cd $DIR/lib/build
cmake ..
make
cd ..
cd ..
mkdir -p build
cd build
cmake ..
make
cp CMData ../..
cp libCMDataDict_rdict.pcm ../..
cp ../moller_ctrl.py ../..
