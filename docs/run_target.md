# Running a Target Program

Here we illustrate how to execute CoFuzz for readelf (binutils-2.37) with [wllvm](https://github.com/travitch/whole-program-llvm).

## Instrumentation

```shell
# Download the source code of binutils-2.37
$ wget https://ftp.gnu.org/gnu/binutils/binutils-2.37.tar.gz
$ tar -xvf binutils-2.38.tar.gz

# Extract the byte code with wllvm (readelf.bc)
$ CC=wllvm LLVM_COMPILER=clang ./configure --disable-shared
$ LLVM_COMPILER=clang make -j$(nproc)
$ cd binutils
$ extract-bc readelf

# The random seed can be set with $AFL_RAND_SEED
$ Trace_CC=clang-10 Trace_CXX=clang++-10 trace/build/clang-trace readelf.bc -o readelf_trace
$ AFL_CC=clang AFL_CXX=clang++ fuzzer/afl-clang-fast readelf.bc -o readelf_afl
$ third_party/concolic/qsym/symcc readelf.bc -o readelf_cohuzz
```



## Running CoFuzz

Here the configure file for readelf (readelf.cfg)

```
[put]
# Program under test
cohuzz_bin=/workspace/CoFuzz/test/readelf_cohuzz
trace_bin=/workspace/CoFuzz/test/readelf_trace
argument=-a @@
```

Running the hybrid fuzzing

```shell
# Running AFL
$ /workspace/CoFuzz/fuzzer/afl-fuzz -m none -i fuzz_in/ -o fuzz_out/ -S afl -- ./readelf_afl -a @@

# Running CoFuzz
$ /workspace/CoFuzz/src/cofuzz.py -c ./readelf.cfg -o fuzz_out/ -a afl
```

