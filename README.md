# CoFuzz
Coordinated hybrid fuzzing framework with advanced coordination mode

## Publication

[Evaluating and Improving Hybrid Fuzzing](https://ieeexplore.ieee.org/document/10172801), ICSE'2023

```
@inproceedings{jiang2023evaluating,
  title = {Evaluating and improving hybrid fuzzing},
  author = {Jiang, Ling and Yuan, Hengchen and Wu, Mingyuan and Zhang, Lingming and Zhang, Yuqun},
  doi = {10.1109/ICSE48619.2023.00045},
  booktitle = {2023 IEEE/ACM 45th International Conference on Software Engineering (ICSE)},
  pages = {410-422},
  year={2023}
}
```

## Build CoFuzz

### Environment

- Tested on Ubuntu 18.04/20.04
- Python (>= 3.8)
- LLVM 10.0-12.0

### Build in local

```shell
$ git submodule update --init --recursive

# Install fuzzer and concolic executor
$ ./build.sh
```


### Build with Docker

We highly recommend to run CoFuzz using the docker container.

```shell
# Build docker image
$ docker build -t cofuzz ./

# Run docker container
$ docker run -itd --privileged cofuzz /bin/bash
```

## Running CoFuzz

### Program instrumentation

CoFuzz compiles the target program into three binaries with seperate instrumentation.

```shell
# Tracing execution path
export CC=trace/build/clang-trace CXX=trace/build/clang-trace++
./configure --disable-shared
make -j$(nproc)

# Count edge coverage for fuzzer
export CC=fuzzer/afl-clang-fast CXX=fuzzer/afl-clang-fast++
./configure --disable-shared
make -j$(nproc)

# Concolic execution
export CC=concolic/qsym/symcc CXX=concolic/qsym/sym++
./configure --disable-shared
make -j$(nproc)
```

### Start Hybrid Fuzzing

For running CoFuzz, a configuration file is required with the following format.

```
[put]
# Program under test
cohuzz_bin=/path/to/binary/for/concolic/exeuction
trace_bin=/path/to/binary/for/trace/path
argument=@@
```

Environment variables:

- **INPUT**: initial seed corpora
- **OUTPUT**: output directory
- **FUZZ_CMD**: command for running program for AFL
- **CFG_FILE**: configuration file for CoFuzz

```shell
# Running fuzzing stratrgy
fuzzer/afl-fuzz -S afl -m none -i $INPUT -o $OUTPUT  -- $FUZZ_CMD

# Running CoFuzz (concolic execution + coordination mode)
src/cofuzz.py -o $OUTPUT -a afl -c $CFG_FILE
```

For running a demo program `readelf`, please turn to the document in [Demo](docs/run_target.md).


## Data

- The data for unique crashes and figures in paper is in [Data](data).
- The assigned CVEs are in [cve](docs/cves.md). Note that the new CVEs are still in the status of *RESERVED*, thus the details are placed here until being published.