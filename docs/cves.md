# CVEs

- [CVE-2022-37165](https://bugzilla.redhat.com/show_bug.cgi?id=2111538)

  Affects program execution, and stable reproduction in the recent versions. The victim must open a specially crafted JPEG file

  `jhead.c - ReadJpegSections - memcmp`


- [CVE-2022-37166](https://github.com/axiomatic-systems/Bento4/issues/732)

  In Bento4 v1.6.0-639 and commit (1f295b8), address points to the zero page in AP4_Track::GetSampleIndexForTimeStampMs and AP4_StsdAtom::AP4_StsdAtom(AP4_SampleTable*) and the corresponding inputs incurred "SEGV on unknown address".

- [CVE-2022-37167](https://github.com/axiomatic-systems/Bento4/issues/734)

   In Bento4 v1.6.0-639 commit (1f295b8), specific input causes heap-buffer-overflow in function AP4_Mp4AudioDecoderConfig::ParseExtension(AP4_Mp4AudioDsiParser&).

- [CVE-2022-37168](https://github.com/axiomatic-systems/Bento4/issues/733)

  Bento4 v1.6.0-639, commit (1f295b8) is vulnerable to SEGV on unknown address via Affected binary -mp4tag.

- [CVE-2022-37169](https://github.com/axiomatic-systems/Bento4/issues/731)

  Bento4 v1.6.0-639, commit (1f295b8) is vulnerable to heap buffer overflow via Affected binary - avcinfo.

- [CVE-2022-37690](https://github.com/axiomatic-systems/Bento4/issues/736)

  The binary program mp4info in Bento4, this problem also have occurred in mp4dump, mp4tag, mp42aac. They are all from function AP4_HvccAtom::AP4_HvccAtom(unsigned int, unsigned char const)*.

- [CVE-2022-37691](https://github.com/axiomatic-systems/Bento4/issues/737)

  Bento4 v1.6.0-639 and commit (df9ba99) is vulnerable to Buffer Overflow. Crafted input in mp4 format causes out-of-memory and memory leaks in mp4split.

- [CVE-2022-38533](https://sourceware.org/bugzilla/show_bug.cgi?id=29482)

  In GNU Binutils before 2.4.0, there is a heap-buffer-overflow in the error function bfd_getl32 when called from the strip_main function in strip-new via a crafted file.
