# Lava-fix

lava-dataset download:http://panda.moyix.net/~moyix/lava_corpus.tar.xz


## Add wrapped functions

 In order for cofuzz to work properly on the lava-m dataset, we need to additionally intercept the I/O functions used in lava-m, , which requires changes to the source code of concolic executor.


### Step1

In `CoFuzz/third_party/concolic/compiler/Runtime.cpp`

Function `bool isInterceptedFunction(const Function &f)` :

#### Before:

```c
bool isInterceptedFunction(const Function &f) {
  static const StringSet<> kInterceptedFunctions = {
      "malloc",   "calloc",  "mmap",    "mmap64", "open",   "read",    "lseek",
      "lseek64",  "fopen",   "fopen64", "fread", "fread_unlocked", "fseek",  "fseeko",  "rewind",
      "fseeko64", "getc",    "ungetc",  "memcpy", "memset", "strncpy", "strchr",
      "memcmp",   "memmove", "ntohl",   "fgets",  "fgetc", "getchar"};

  return (kInterceptedFunctions.count(f.getName()) > 0);
}

```

Add function: **fread_unlocked, freopen, getc_unlocked, getline, getutxent.**


#### After:

```c
bool isInterceptedFunction(const Function &f) {
  static const StringSet<> kInterceptedFunctions = {
      "malloc",   "calloc",  "mmap",    "mmap64", "open",   "read",    "lseek",
      "lseek64",  "fopen",   "fopen64", "fread",  "fread_unlocked", "fseek",  "fseeko",  "rewind", "freopen",
      "fseeko64", "getc",  "getc_unlocked", "ungetc",  "memcpy", "memset", "strncpy", "strchr","getline","getutxent",
      "memcmp",   "memmove", "ntohl",   "fgets",  "fgetc", "getchar"};

  return (kInterceptedFunctions.count(f.getName()) > 0);
}

```


### Step2

In `CoFuzz/third_party/concolic/runtime/LibcWrappers.cpp`

Add the function bodies mentioned in **Step1** in namespace.


**getuxtent:**

```c
  struct utmpx *SYM(getutxent)()
  {
    auto *result = getutxent();
    _sym_set_return_expression(nullptr);

    // Reading symbolic input.
    ReadWriteShadow shadow(result, sizeof (struct utmpx));
    std::generate(shadow.begin(), shadow.end(),
                  []()
                  { return _sym_get_input_byte(inputOffset++); });

    return result;
  }
```



**fread_unlocked:**

```c
size_t SYM(fread_unlocked)(void *ptr, size_t size, size_t nmemb, FILE *stream)
  {
    tryAlternative(ptr, _sym_get_parameter_expression(0), SYM(fread));
    tryAlternative(size, _sym_get_parameter_expression(1), SYM(fread));
    tryAlternative(nmemb, _sym_get_parameter_expression(2), SYM(fread));

    auto result = fread(ptr, size, nmemb, stream);
    _sym_set_return_expression(nullptr);

    if (fileno(stream) == inputFileDescriptor)
    {
      // Reading symbolic input.
      ReadWriteShadow shadow(ptr, result * size);
      std::generate(shadow.begin(), shadow.end(),
                    []()
                    { return _sym_get_input_byte(inputOffset++); });
    }
    else if (!isConcrete(ptr, result * size))
    {
      ReadWriteShadow shadow(ptr, result * size);
      std::fill(shadow.begin(), shadow.end(), nullptr);
    }

    return result;
  }
```


**getline**:

```c
ssize_t SYM(getline)(char **ptr, size_t *n, FILE *stream)
  {

    tryAlternative(ptr, _sym_get_parameter_expression(0), SYM(getline));
    tryAlternative(n, _sym_get_parameter_expression(1), SYM(getline));
    // tryAlternative(stream, _sym_get_parameter_expression(2), SYM(fread));

    auto result = getdelim(ptr, n, '\n', stream);
    
    _sym_set_return_expression(nullptr);

    if (fileno(stream) == inputFileDescriptor)
    {
      // Reading symbolic input.
      ReadWriteShadow shadow(*ptr, result * (*n + 1));
      std::generate(shadow.begin(), shadow.end(),
                    []()
                    { return _sym_get_input_byte(inputOffset++); });
    }
    else if (!isConcrete(*ptr, result * (*n + 1)))
    {
      ReadWriteShadow shadow(*ptr, result * (*n + 1));
      std::fill(shadow.begin(), shadow.end(), nullptr);
    }

    return result;
  }
```


**freopen:**

```c
  FILE *SYM(freopen)(const char *filename, const char *mode, FILE *stream)
  {
    auto *result = freopen(filename, mode, stream);
    _sym_set_return_expression(nullptr);
    if (result != nullptr && !g_config.fullyConcrete &&
        !g_config.inputFile.empty() &&
        strstr(filename, g_config.inputFile.c_str()) != nullptr)
    {
      if (inputFileDescriptor != -1)
        std::cerr << "Warning: input file opened multiple times; this is not yet "
                     "supported"
                  << std::endl;
      inputFileDescriptor = fileno(result);
      inputOffset = 0;
    }

    return result;
  }
```


**getc_unlocked:**

```c
  int SYM(getc_unlocked)(FILE *stream)
  {
    auto result = getc(stream);
    if (result == EOF)
    {
      _sym_set_return_expression(nullptr);
      return result;
    }

    if (fileno(stream) == inputFileDescriptor)
      _sym_set_return_expression(_sym_build_zext(
          _sym_get_input_byte(inputOffset++), sizeof(int) * 8 - 8));
    else
      _sym_set_return_expression(nullptr);

    return result;
  }
```


## Extra fixes

After the above fixes, some binary for concolic execution may still not work properly, you can make the following additional fixes to the corresponding program.


### Extra fix for uniq

run below codes after configuration:

```shell
find . -type f -name "*.h" -exec sed -i 's/#define\s*HAVE_GETC_UNLOCKED\s*[0-9]/#undef HAVE_GETC_UNLOCKED/' {} +
find . -type f -name "*.h" -exec sed -i 's/#define\s*HAVE_DECL_GETC_UNLOCKED\s*[0-9]/#undef HAVE_GETC_UNLOCKED/' {} +
```


### **Extra fix for who**

The original function **lava_get** in  **who** may not output the triggered bug number correctly, so we need to make the following changes to the **lava_get** function in **who**’s source code:

```c
// move to somewhere after #include "..."
unsigned int lava_get(unsigned int bug_num) {

#define SWAP_UINT32(x) (((x) >> 24) | (((x) & 0x00FF0000) >> 8) | (((x) & 0x0000FF00) << 8) | ((x) << 24))
  if (0x6c617661 - bug_num == lava_val[bug_num] ||
      SWAP_UINT32(0x6c617661 - bug_num) == lava_val[bug_num]) {
    printf("Successfully triggered bug %d, crashing now!\n", bug_num);
    fflush(0);
    //exit(0);
  }
  else {
    //printf("Not successful for bug %d; val = %08x not %08x or %08x\n", bug_num, lava_val[bug_num], 0x6c617661 + bug_num, 0x6176616c + bug_num);
  }
  return lava_val[bug_num];
}
```
