FROM ubuntu:20.04

RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y git clang-10 llvm-10-dev llvm-10-tools \
    cmake g++ ninja-build libz3-dev python2 python3-pip zlib1g-dev libacl1-dev libpcap-dev   \
    libboost-all-dev libeigen3-dev swig

WORKDIR /workspace

RUN git clone https://github.com/Tricker-z/CoFuzz.git && \
    cd CoFuzz &&                                         \
    git submodule update --init --recursive &&           \
    ./build.sh
