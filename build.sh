#!/bin/bash

base_path=`pwd`
mkdir /tmp/output
pip3 install -r requirements.txt

# Build fuzzer AFL-2.57
pushd fuzzer
make -j$(nproc)
LLVM_CONFIG=llvm-config-10 CC=clang-10 CXX=clang++-10 make -j$(nproc) -C llvm_mode

# Build tracer
pushd $base_path
LLVM_CONFIG=llvm-config-10 CC=clang-10 CXX=clang++-10 make -j$(nproc) -C trace

# Build SMT-solver z3
pushd $base_path/third_party/z3
git checkout z3-4.8.12
python3 scripts/mk_make.py
pushd build
make -j$(nproc)
make install

# Build concolic executor with QSYM backend
pushd $base_path/third_party/concolic
mkdir qsym
pushd qsym
CC=clang-10 CXX=clang++-10 cmake -G Ninja     \
    -DQSYM_BACKEND=ON                         \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo         \
    -DZ3_TRUST_SYSTEM_VERSION=on              \
    -DLLVM_DIR=/usr/lib/llvm-10/cmake         \
    -DZ3_DIR=/workspace/CoFuzz/third_party/z3 \
    ../
ninja all

# Build sample algorithms
pushd $base_path/third_party/vaidya-walk/code
cp -r /usr/include/eigen3/Eigen /usr/local/include
python3 setup.py install
cp pwalk.py /usr/local/lib/python3.8/dist-packages/
