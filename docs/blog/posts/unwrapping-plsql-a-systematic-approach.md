---
categories:
  - Oracle
date:
  created: 2019-09-06T22:00:00
description: >-
  Demonstrates using the Oracle Wrap substitution table participating in the PL/SQL wrap process by reverse engineering Oracle binaries.
tags:
  - Code symbol
  - PL/SQL
---

# Unwrapping PL/SQL: a Systematic Approach

In this blog post, I will show how I discovered the Oracle Wrap substitution table by reverse engineering Oracle binaries.

<!-- more -->

## Wrap process

The high-level steps of how PL/SQL code appears to be wrapped since 10g on are below:

1. The source code is ***normalized*** (converted to upper-case, comments are removed, etc.)
1. The normalized code is compressed using ZIP
1. The compressed byte stream is obfuscated using a substitution table
1. Finally, Base64 encoding is applied

If we want to rewind that process and get the unwrapped code, the best we can do is to get the ***normalized*** code.
Steps 4 (Base64 Encoding) and 2 (ZIP Compression) are reversible, however, the obfuscation step 3 supposedly uses a substitution table which is the secret sauce of the Oracle Wrap process.

## Brute-force approach

It is known how to obtain that wrap substitution table using a kind of a brute-force approach, as it was demonstrated in the following links:

- [Unwrapping Oracle PLSQL](https://macrotoneconsulting.co.uk/images/Documents/unwrap.pdf)
- [Unwrapping 10G wrapped PL/SQL by Anton Scheffer](https://technology.amis.nl/2009/02/03/unwrapping-10g-wrapped-plsql/)

Once the substitution table is known, it becomes feasible to write a fully-fledged unwrapper.
See for example: [Unwrapping Oracle PL/SQL with unwrap.py by Niels Teusink](http://blog.teusink.net/2010/04/unwrapping-oracle-plsql-with-unwrappy.html)

I will be using that code that Anton Scheffer referred to in his [blog post](https://technology.amis.nl/wp-content/uploads/file/generate2.txt), namely I need to be able to compress and decompress data in SQL:

```sql
create or replace java source named MY_COMPRESS
as
import java.io.*;
import java.util.zip.*;

public class MY_COMPRESS
{
  public static String Inflate( byte[] src )
  {
    try
    {
      ByteArrayInputStream bis = new ByteArrayInputStream( src );
      InflaterInputStream iis = new InflaterInputStream( bis );
      StringBuffer sb = new StringBuffer();
      for( int c = iis.read(); c != -1; c = iis.read() )
      {
        sb.append( (char) c );
      }
      return sb.toString();
    } catch ( Exception e )
    {
    }
    return null;
  }
  public static byte[] Deflate( String src, int quality )
  {
    try
    {
      byte[] tmp = new byte[ src.length() + 100 ];
      Deflater defl = new Deflater( quality );
      defl.setInput( src.getBytes( "UTF-8" ) );
      defl.finish();
      int cnt = defl.deflate( tmp );
      byte[] res = new byte[ cnt ];
      for( int i = 0; i < cnt; i++ )
        res[i] = tmp[i];
      return res;
    } catch ( Exception e )
    {
    }
    return null;
  }
}
/

alter java source MY_COMPRESS compile
/

create or replace package mycompress
is
  function deflate( src in varchar2 )
  return raw;
--
  function deflate( src in varchar2, quality in number )
  return raw;
--
  function inflate( src in raw )
  return varchar2;
--
end;
/

create or replace package body mycompress
is
  function deflate( src in varchar2 )
  return raw
  is
  begin
    return deflate( src, 6 );
  end;
--
  function deflate( src in varchar2, quality in number )
  return raw
  as language java
  name 'MY_COMPRESS.Deflate( java.lang.String, int ) return byte[]';
--
  function inflate( src in raw )
  return varchar2
  as language java
  name 'MY_COMPRESS.Inflate( byte[] ) return java.lang.String';
--
end;
/
```

Let's now obtain some data for analysis that will be used throughout this post:

```sql
SQL> with src as (
  2    select 'FUNCTION F RETURN NUMBER IS BEGIN RETURN 1; END;' txt
  3      from dual),
  4  wrap as (
  5    select src.txt,
  6           dbms_ddl.wrap( 'CREATE OR REPLACE ' || src.txt) wrap
  7      from src),
  8  subst as (
  9    select substr(utl_encode.base64_decode(utl_raw.cast_to_raw(rtrim(substr(wrap.wrap, instr(wrap.wrap,
 chr(10), 1, 20) + 1), chr(10)))), 41) x,
 10           mycompress.deflate(wrap.txt||chr(0)) d
 11      from wrap)
 12  select to_number(substr(x, r*2 -1,2), 'xx') wrapped,
 13         substr(x, r*2 -1, 2) wrapped_hex,
 14         to_number(substr(d, r*2 -1,2), 'xx') zipped,
 15         substr(d, r*2 -1, 2) zipped_hex
 16    from subst,
 17         (select rownum r from dual connect by rownum <= 10);

   WRAPPED WRAPPED_HEX     ZIPPED ZIPPED_HEX
---------- ----------- ---------- -----------
        48 30                 120 78
       131 83                 156 9C
       199 C7                 115 73
       153 99                  11 0B
       129 81                 245 F5
       199 C7                 115 73
       203 CB                  14 0E
         8 08                 241 F1
       210 D2                 244 F4
       254 FE                 247 F7
```

The `ZIPPED_HEX` column shows compressed bytes whereas `WRAPPED_HEX` shows the corresponding wrapped byte.
A simple brute-force approach can be used to obtain the reverse wrap substitution table to convert a wrapped byte to its corresponding zipped byte.
Then, it is just enough to unzip the final byte stream to complete the unwrap exercise.

## Systematic approach

I was curious how to do the same by using a more systematic approach.
For that, I was recording the function calls using DebugTrace from [the Intel Pin Tools](https://software.intel.com/en-us/articles/pin-a-dynamic-binary-instrumentation-tool) of a session wrapping PL/SQL code.
I came across the `pkwrap_obfuscate_source` function:

```
pkwrap_obfuscate_source(0x7feb38878af8, 0x9, ...)
> bam_init(0x7feb38878af8, 0x7ffd567e9d18, ...)
| > kghalp(0x7feb3e4a69a0, 0x7feb3e4abe00, ...)
| | > kghprmalo(0x7feb3e4a69a0, 0, ...)
| | | > kghtshrt(0x7feb3e4a69a0, 0, ...)
| | | < kghtshrt+0x000000000169 returns: 0x40b38f0000000139
| | | > kghfnd_in_free_lists(0x7feb3e4a69a0, 0, ...)
| | | < kghfnd_in_free_lists+0x0000000001d5 returns: 0
| | | > kghfnd(0x7feb3e4a69a0, 0, ...)
| | | | > kghgex(0x7feb3e4a69a0, 0, ...)
| | | | | > kghalo(0x7feb3e4a69a0, 0x7feb3e4ad700, ...)
| | | | | | > kghfnd_in_free_lists(0x7feb3e4a69a0, 0, ...)
| | | | | | < kghfnd_in_free_lists+0x0000000001d5 returns: 0x7feb3e37bc00
| | | | | | > kghbshrt(0x7feb3e4a69a0, 0, ...)
| | | | | | < kghbshrt+0x000000000130 returns: 0x7feb3e37dbc8
| | | | | | > ksmpga_allo_cb(0x7feb3e4a69a0, 0x7feb3e4ad700, ...)
| | | | | | | > ksm_near_pga_limit_pdb(0x1, 0x3, ...)
| | | | | | | < ksm_near_pga_limit_pdb+0x00000000017f returns: 0
| | | | | | < ksmpga_allo_cb+0x0000000006a4 returns: 0
| | | | | < kghalo+0x000000000722 returns: 0x7feb3e37dbe0
| | | | | > kghaddex(0x7feb3e4a69a0, 0, ...)
| | | | | < kghaddex+0x00000000026a returns: 0x7feb3e37dbf0
| | | | < kghgex+0x00000000034e returns: 0x7feb3e37dbf0
| | | < kghfnd+0x00000000018b returns: 0x7feb3e37dbf0
| | < kghprmalo+0x00000000045e returns: 0x7feb3e37dc18
| | > _intel_fast_memset(0x7feb3e37dc18, 0, ...)
| | <> _intel_fast_memset.J(0x7feb3e37dc18, 0, ...)
| | <> __intel_memset(0x7feb3e37dc18, 0, ...)
| | < __intel_memset+0x000000000818 returns: 0x7feb3e37dc18
| < kghalp+0x0000000002d9 returns: 0x7feb3e37dc18
< bam_init+0x000000000105 returns: 0x7ffd567e9d18
```

It is coming from the `pkwrap.o` object file within the `$ORACLE_HOME/lib/libpls12.a` archive.
There is one especially interesting line in that file:

``` hl_lines="17"
$ objdump -dzr pkwrap.o

    4ecd:       ff c3                   inc    %ebx
    4ecf:       89 d8                   mov    %ebx,%eax
    4ed1:       83 fb 14                cmp    $0x14,%ebx
    4ed4:       72 de                   jb     4eb4 <pkwrap_obfuscate_source+0x194>
    4ed6:       48 8b 55 c8             mov    -0x38(%rbp),%rdx
    4eda:       33 c9                   xor    %ecx,%ecx
    4edc:       48 8b 45 e0             mov    -0x20(%rbp),%rax
    4ee0:       48 85 c0                test   %rax,%rax
    4ee3:       48 89 55 d0             mov    %rdx,-0x30(%rbp)
    4ee7:       76 27                   jbe    4f10 <pkwrap_obfuscate_source+0x1f0>
    4ee9:       0f b6 04 0a             movzbl (%rdx,%rcx,1),%eax
    4eed:       48 83 c0 a0             add    $0xffffffffffffffa0,%rax
    4ef1:       0f b6 d8                movzbl %al,%ebx
    4ef4:       44 8a 83 00 00 00 00    mov    0x0(%rbx),%r8b
                        4ef7: R_X86_64_32S      pkwrap_forward_table
```

`R_X86_64_32S` is one of relocation types as it is defined in [System V Application Binary Interface](http://refspecs.linuxbase.org/elf/x86_64-abi-0.98.pdf).
Here is how to get that table:

``` hl_lines="26 30"
$ readelf --syms pkwrap.o

Symbol table '.symtab' contains 94 entries:
   Num:    Value          Size Type    Bind   Vis      Ndx Name
     0: 0000000000000000     0 NOTYPE  LOCAL  DEFAULT  UND
     1: 0000000000000000     0 FILE    LOCAL  DEFAULT  ABS pkwrap.c
     2: 0000000000000000     0 SECTION LOCAL  DEFAULT    2
     3: 0000000000000000     0 SECTION LOCAL  DEFAULT    3
     4: 0000000000000000     0 SECTION LOCAL  DEFAULT    4
     5: 0000000000000000     0 SECTION LOCAL  DEFAULT    5
     6: 0000000000000000     0 SECTION LOCAL  DEFAULT    6
     7: 0000000000000010    80 FUNC    LOCAL  DEFAULT    6 pkwrap_skip_white_space
     8: 0000000000000060   304 FUNC    LOCAL  DEFAULT    6 pkwrap_read_hex
     9: 0000000000000000     0 SECTION LOCAL  DEFAULT    7
    10: 0000000000000190   272 FUNC    LOCAL  DEFAULT    6 pkwrap_read_hex_multi
    11: 00000000000002a0  3440 FUNC    LOCAL  DEFAULT    6 pkwrap_read_string
    12: 0000000000001010   896 FUNC    LOCAL  DEFAULT    6 pkwrap_read_string_paro
    13: 0000000000001390   192 FUNC    LOCAL  DEFAULT    6 pkwrap_read_number
    14: 0000000000001450   416 FUNC    LOCAL  DEFAULT    6 pkwrap_read_number_paro
    15: 00000000000015f0   400 FUNC    LOCAL  DEFAULT    6 pkwrap_2_to_4
    16: 0000000000001780   384 FUNC    LOCAL  DEFAULT    6 pkwrap_4_to_8
    17: 0000000000001900   976 FUNC    LOCAL  DEFAULT    6 pkwrap_read_ub_paro
    18: 0000000000001cd0   736 FUNC    LOCAL  DEFAULT    6 pkwrap_read_symtab
    19: 0000000000001fb0  1728 FUNC    LOCAL  DEFAULT    6 pkwrap_read_source
    20: 0000000000000000     0 SECTION LOCAL  DEFAULT    8
    21: 0000000000000080   256 OBJECT  LOCAL  DEFAULT    8 pkwrap_reverse_table
    22: 0000000000003cc0  4192 FUNC    LOCAL  DEFAULT    6 pkwrap_is_plsql
    23: 0000000000000000     0 SECTION LOCAL  DEFAULT    9
    24: 0000000000004d20  1072 FUNC    LOCAL  DEFAULT    6 pkwrap_obfuscate_source
    25: 0000000000000180   256 OBJECT  LOCAL  DEFAULT    8 pkwrap_forward_table
```

Those tables are coming from section 8 and start at addresses `0x00000080` (`pkwrap_reverse_table`) and `0x00000180` (`pkwrap_forward_table`).
The aforementioned section can be seen as follows:

``` hl_lines="13 29"
$readelf --hex-dump=8 pkwrap.o

Hex dump of section '.rodata':
 NOTE: This section has relocations against it, but these have NOT been applied to this dump.
  0x00000000 00000000 00000000 00000000 00000000 ................
  0x00000010 00000000 00000000 00000000 00000000 ................
  0x00000020 00000000 00000000 00000000 00000000 ................
  0x00000030 00000000 00000000 00000000 00000000 ................
  0x00000040 00000000 00000000 00000000 00000000 ................
  0x00000050 00000000 00000000 00000000 00000000 ................
  0x00000060 00000000 00000000 00000000 00000000 ................
  0x00000070 00000000 00000000 00000000 00000000 ................
  0x00000080 dd052553 b87b8227 91f24b03 eb5540ff ..%S.{.'..K..U@.
  0x00000090 1d081b3b c462c807 2a7e44c6 bea38bb7 ...;.b..*~D.....
  0x000000a0 0fd4de1a df72490a af89d5f6 bf51edb0 .....rI......Q..
  0x000000b0 18791596 5ce1a421 01a6994d 7675c91e .y..\..!...Mvu..
  0x000000c0 263e1985 a55a246c 0ec72e50 fd48933f &>...Z$l...P.H.?
  0x000000d0 70421158 f87dccd8 39ece8a7 f584f32c pB.X.}..9......,
  0x000000e0 e656cd45 4fd2c2e0 7cf06341 c52b3cb6 .V.EO...|.cA.+<.
  0x000000f0 00fc6f9d ac38bc74 d70ddcda d0880cd1 ..o..8.t........
  0x00000100 e795d37a e36883fe b9348c86 4335b480 ...z.h...4..C5..
  0x00000110 3d049af9 b565cf6a 5bab7f92 375faa16 =....e.j[...7_..
  0x00000120 54e9e4fa bd90a036 c1201fba 22d9ef61 T......6. .."..a
  0x00000130 4777ad71 789fb333 108efb8f 5ea95917 Gw.qx..3....^.Y.
  0x00000140 128752f4 57ca6713 3006c0ae f18d981c ..R.W.g.0.......
  0x00000150 2fce94b2 66cb236d 4c6bdb64 ee6009d6 /...f.#mLk.d.`..
  0x00000160 02a24e28 9c4ae2a8 46e5f773 3a5d81c3 ..N(.J..F..s:]..
  0x00000170 2d32eab1 29140b31 9b9e69a1 8abb976e -2..)..1..i....n
  0x00000180 7038e00b 9101c917 11de27f6 7e794820 p8........'.~yH
  0x00000190 b852c0c7 f5329fbf 30422312 cf103faa .R...2..0B#...?.
  0x000001a0 a937acd6 46024007 e3f4186d 5ff04ad0 .7..F.@....m_.J.
  0x000001b0 c8f7f1b7 898da79c 7558ec13 6e90414f ........uX..n.AO
  0x000001c0 0e6b518c 1a63e8b0 4d26e50a d83be264 .kQ..c..M&...;.d
  0x000001d0 4b2dc203 a00d61c4 53be4598 34edbc9d K-....a.S.E.4...
  0x000001e0 ddaf156a db95d4c6 85fa97d9 47d7ff72 ...j........G..r
  0x000001f0 50b325eb 773d3cb1 b4318305 6855199a P.%.w=<..1..hU..
  0x00000200 8fee0686 5d438bc1 7d29fc1e 8acdb9bb ....]C..})......
  0x00000210 a5089b4e d28133fe ce3a92f8 e473f9b5 ...N..3..:...s..
  0x00000220 a6fbe11d 3644395b e7bd9e99 74b2cb28 ....6D9[....t..(
  0x00000230 2ff3d3b6 8e946f1f 0488abfd 76a41c2c /.....o.....v..,
  0x00000240 caa866ef 146c1b49 163ec5d5 5662d196 ..f..l.I.>..Vb..
  0x00000250 7c7f6582 212adf78 57ad7bda 7a002224 |.e.!*.xW.{.z."$
  0x00000260 6735e684 a2e96080 5aa1f20c 592edcae g5....`.Z...Y...
  0x00000270 69cc095e c35c2bea 5493a3ba 714c870f i..^.\+.T...qL..
  0x00000280 9a999999 9999f13f 00000000 00002840 .......?......(@
  0x00000290 00000000 00003440 66666666 6666f63f ......4@ffffff.?
  0x000002a0 00000000 0000e043 0000005f 00000000 .......C..._....
  0x000002b0 00000000 00000000 00000000 00000000 ................
```

Judging by their names:

- `pkwrap_forward_table` should be applied at [step 3](#wrap-process) when the zipped byte stream is converted using the substitution table.
- `pkwrap_reverse_table` can be used to reverse that step.

Initially, I could not find out how both of those tables are used.
Then, while I was studying the `pkwrap_obfuscate_source` procedure in [Ghidra](https://ghidra-sre.org/), I found a block of code that seemed quite promising:

```c hl_lines="4"
if (CONCAT44(uStack36,local_28) != 0) {
    do {
      *(undefined *)(local_40 + uVar7) =
           pkwrap_forward_table[(ulong)(byte)(*(char *)(local_40 + uVar7) + 0xa0)];
      uVar7 = (ulong)((int)uVar7 + 1);
    } while (uVar7 < CONCAT44(uStack36,local_28));
  }
```

The important part here is how that table is accessed - there is `0xA0` which is 160 in decimal.
Let's just try to lookup those zipped bytes against `pkwrap_forward_table` by adding that offset `0xA0` to them:

```sql
SQL> with src as (
  2    select 'FUNCTION F RETURN NUMBER IS BEGIN RETURN 1; END;' txt
  3      from dual),
  4  wrap as (
  5    select src.txt,
  6           dbms_ddl.wrap( 'CREATE OR REPLACE ' || src.txt) wrap
  7      from src),
  8  subst as (
  9    select substr(utl_encode.base64_decode(utl_raw.cast_to_raw(rtrim(substr(wrap.wrap, instr(wrap.wrap,
 chr(10), 1, 20) + 1), chr(10)))), 41) x,
 10           mycompress.deflate(wrap.txt||chr(0)) d
 11      from wrap)
 12  select to_number(substr(x, r*2 -1,2), 'xx') wrapped,
 13         substr(x, r*2 -1, 2) wrapped_hex,
 14         to_number(substr(d, r*2 -1,2), 'xx') zipped,
 15         substr(d, r*2 -1, 2) zipped_hex
 16    from subst,
 17         (select rownum r from dual connect by rownum <= 10);

   WRAPPED WRAPPED_HEX     ZIPPED ZIPPED_HEX
---------- ----------- ---------- -----------
        48 30                 120 78
       131 83                 156 9C
       199 C7                 115 73
       153 99                  11 0B
       129 81                 245 F5
       199 C7                 115 73
       203 CB                  14 0E
         8 08                 241 F1
       210 D2                 244 F4
       254 FE                 247 F7
```

I got the following table:

| WRAPPED\_HEX | ZIPPED\_HEX | MOD(ZIPPED\_HEX+0xA0,0x100) | PKWRAP\_FORWARD\_TABLE(MOD(ZIPPED\_HEX+0xA0,0x100)) |
| ------------ | ----------- | --------------------------- | --------------------------------------------------- |
| 0x30 | 0x78 | 0x18 | 0x30 |
| 0x83 | 0x9C | 0x3C | 0x6E |
| 0xC7 | 0x78 | 0x73 | 0xC7 |
| 0x99 | 0x0B | 0xAB | 0x99 |
| 0x81 | 0xF5 | 0x95 | 0x81 |
| 0xC7 | 0x78 | 0x73 | 0xC7 |
| 0xCB | 0x0E | 0xAE | 0xCB |
| 0x08 | 0xF1 | 0x91 | 0x08 |
| 0xD2 | 0xF4 | 0x94 | 0xD2 |
| 0xFE | 0xF7 | 0x97 | 0xFE |

Let me explain how the right most column is obtained. I will take the last row for this example.
The wrapped byte is `0xFE`, its corresponding zipped byte is `0xF7`.
`MOD(0xF7 + 0xA0, 0x100)=0x97`.
The relevant entry from `pkwrap_forward_table` at index `0x97` is `0xFE` (the same as the wrapped byte):

``` hl_lines="10"
  0x00000180 7038e00b 9101c917 11de27f6 7e794820 p8........'.~yH
  0x00000190 b852c0c7 f5329fbf 30422312 cf103faa .R...2..0B#...?.
  0x000001a0 a937acd6 46024007 e3f4186d 5ff04ad0 .7..F.@....m_.J.
  0x000001b0 c8f7f1b7 898da79c 7558ec13 6e90414f ........uX..n.AO
  0x000001c0 0e6b518c 1a63e8b0 4d26e50a d83be264 .kQ..c..M&...;.d
  0x000001d0 4b2dc203 a00d61c4 53be4598 34edbc9d K-....a.S.E.4...
  0x000001e0 ddaf156a db95d4c6 85fa97d9 47d7ff72 ...j........G..r
  0x000001f0 50b325eb 773d3cb1 b4318305 6855199a P.%.w=<..1..hU..
  0x00000200 8fee0686 5d438bc1 7d29fc1e 8acdb9bb ....]C..})......
  0x00000210 a5089b4e d28133fe ce3a92f8 e473f9b5 ...N..3..:...s..
  0x00000220 a6fbe11d 3644395b e7bd9e99 74b2cb28 ....6D9[....t..(
  0x00000230 2ff3d3b6 8e946f1f 0488abfd 76a41c2c /.....o.....v..,
  0x00000240 caa866ef 146c1b49 163ec5d5 5662d196 ..f..l.I.>..Vb..
  0x00000250 7c7f6582 212adf78 57ad7bda 7a002224 |.e.!*.xW.{.z."$
  0x00000260 6735e684 a2e96080 5aa1f20c 592edcae g5....`.Z...Y...
  0x00000270 69cc095e c35c2bea 5493a3ba 714c870f i..^.\+.T...qL..
```

!!! note

    I have no explanation right now why there is a discrepancy in the second line of the table.

## Unwrapping sample code

As it has been shown `pkwrap_forward_table` can be used to convert compressed byte stream to wrapped bytes, it is now possible to obtain the reverse table that can be used to unwrap stored PL/SQL code (the secret sauce of the Oracle Wrap process that is known to be obtained using a brute-force algorithm):

```sql
SQL> declare
  2    v_forward_table raw(256) :=
  3      hextoraw('7038e00b9101c91711de27f67e794820'||
  4               'b852c0c7f5329fbf30422312cf103faa'||
  5               'a937acd646024007e3f4186d5ff04ad0'||
  6               'c8f7f1b7898da79c7558ec136e90414f'||
  7               '0e6b518c1a63e8b04d26e50ad83be264'||
  8               '4b2dc203a00d61c453be459834edbc9d'||
  9               'ddaf156adb95d4c685fa97d947d7ff72'||
 10               '50b325eb773d3cb1b43183056855199a'||
 11               '8fee06865d438bc17d29fc1e8acdb9bb'||
 12               'a5089b4ed28133fece3a92f8e473f9b5'||
 13               'a6fbe11d3644395be7bd9e9974b2cb28'||
 14               '2ff3d3b68e946f1f0488abfd76a41c2c'||
 15               'caa866ef146c1b49163ec5d55662d196'||
 16               '7c7f6582212adf7857ad7bda7a002224'||
 17               '6735e684a2e960805aa1f20c592edcae'||
 18               '69cc095ec35c2bea5493a3ba714c870f');
 19    type wrap_table_type is table of raw(1) index by pls_integer;
 20    v_reverse_table wrap_table_type;
 21    procedure populate_reverse_table
 22    is
 23      v_byte raw(1);
 24      v_index pls_integer;
 25    begin
 26      for i in 0..255
 27      loop
 28        v_index := i;
 29        v_byte := utl_raw.substr(v_forward_table, v_index + 1, 1);
 30        v_reverse_table(to_number(rawtohex(v_byte),'XX')):=hextoraw(to_char(mod(v_index - 160 + 256, 25
6), 'fm0X'));
 31      end loop;
 32    end populate_reverse_table;
 33    procedure print_reverse_table
 34    is
 35    begin
 36      for i in 0..255
 37      loop
 38        if mod(i,16)=0
 39        then
 40          dbms_output.new_line();
 41        end if;
 42        dbms_output.put(lower(rawtohex(v_reverse_table(i))));
 43      end loop;
 44      dbms_output.new_line();
 45    end print_reverse_table;
 46  begin
 47    populate_reverse_table();
 48    print_reverse_table();
 49  end;
 50  /
3d6585b318dbe287f152ab634bb5a05f
7d687b9b24c228678adea4261e03eb17
6f343e7a3fd2a96a0fe935561fb14d10
78d975f6bc4104816106f9add6d5297e
869e79e505ba84cc6e278eb05da8f39f
d0a271b858dd2c38994c480755e4538c
46b62da5af322240dc50c3a1258b9c16
605ccffd0c981cd4376d3c3a30e86c31
47f533da43c8e35e1994ece6a39514e0
9d64fa5915c52fcabb0bdff297bf0a76
b449445a1df0009621807f1a82394fc1
a7d70dd1d8ff139370ee5befbe09b977
72e7b254b72ac7739066200e51edf87c
8f2ef412c62b83cdaccb3bc44ec06936
6202ae88fcaa4208a64557d39abde123
8d924a1189746b91fbfec901ea1bf7ce

PL/SQL procedure successfully completed.
```

Now I can try to rewrap a sample piece of code using that substitution table:

```sql
SQL> with src as (
  2    select q'!package body test_pkg
  3  is
  4  procedure p1
  5  is
  6     v_local_var pls_integer := 10;
  7  begin
  8    dbms_output.put_line(123);
  9  end;
 10  function f1 return varchar2
 11  is
 12    /* code comment*/
 13  begin
 14    return 'string';
 15  end;
 16  end;!' txt
 17      from dual),
 18    wrap as (
 19      select dbms_ddl.wrap( 'create ' || src.txt ) wrap
 20        from src),
 21    base64_dcd as(
 22      select substr( utl_encode.base64_decode( utl_raw.cast_to_raw(rtrim( substr( wrap.wrap, instr( wra
p.wrap, chr( 10 ), 1, 20 ) + 1 ), chr(10) )  ) ), 41 ) x
 23        from wrap),
 24    subst as (
 25      select utl_raw.translate( x,
 26               hextoraw('000102030405060708090A0B0C0D0E0F' ||
 27                        '101112131415161718191A1B1C1D1E1F' ||
 28                        '202122232425262728292A2B2C2D2E2F' ||
 29                        '303132333435363738393A3B3C3D3E3F' ||
 30                        '404142434445464748494A4B4C4D4E4F' ||
 31                        '505152535455565758595A5B5C5D5E5F' ||
 32                        '606162636465666768696A6B6C6D6E6F' ||
 33                        '707172737475767778797A7B7C7D7E7F' ||
 34                        '808182838485868788898A8B8C8D8E8F' ||
 35                        '909192939495969798999A9B9C9D9E9F' ||
 36                        'A0A1A2A3A4A5A6A7A8A9AAABACADAEAF' ||
 37                        'B0B1B2B3B4B5B6B7B8B9BABBBCBDBEBF' ||
 38                        'C0C1C2C3C4C5C6C7C8C9CACBCCCDCECF' ||
 39                        'D0D1D2D3D4D5D6D7D8D9DADBDCDDDEDF' ||
 40                        'E0E1E2E3E4E5E6E7E8E9EAEBECEDEEEF' ||
 41                        'F0F1F2F3F4F5F6F7F8F9FAFBFCFDFEFF'),
 42               hextoraw('3D6585B318DBE287F152AB634BB5A05F' ||
 43                        '7D687B9B24C228678ADEA4261E03EB17' ||
 44                        '6F343E7A3FD2A96A0FE935561FB14D10' ||
 45                        '78D975F6BC4104816106F9ADD6D5297E' ||
 46                        '869E79E505BA84CC6E278EB05DA8F39F' ||
 47                        'D0A271B858DD2C38994C480755E4538C' ||
 48                        '46B62DA5AF322240DC50C3A1258B9C16' ||
 49                        '605CCFFD0C981CD4376D3C3A30E86C31' ||
 50                        '47F533DA43C8E35E1994ECE6A39514E0' ||
 51                        '9D64FA5915C52FCABB0BDFF297BF0A76' ||
 52                        'B449445A1DF0009621807F1A82394FC1' ||
 53                        'A7D70DD1D8FF139370EE5BEFBE09B977' ||
 54                        '72E7B254B72AC7739066200E51EDF87C' ||
 55                        '8F2EF412C62B83CDACCB3BC44EC06936' ||
 56                        '6202AE88FCAA4208A64557D39ABDE123' ||
 57                        '8D924A1189746B91FBFEC901EA1BF7CE')) s
 58      from base64_dcd)
 59  select mycompress.inflate( s ) unwrapped_code
 60    from subst
 61  /

UNWRAPPED_CODE
--------------------------------------------------------------------------------
PACKAGE BODY test_pkg
IS
PROCEDURE P1
IS
   V_LOCAL_VAR PLS_INTEGER := 10;
BEGIN
  DBMS_OUTPUT.PUT_LINE(123);
END;
FUNCTION F1 RETURN VARCHAR2
IS

BEGIN
  RETURN 'string';
END;
END;
```

Therefore, it has been demonstrated that the reverse table obtained with a help of `pkwrap_forward_table` can be used to unwrap this sample piece of PL/SQL code.

## pkwrap\_reverse\_table

Going back to `pkwrap_reverse_table`, let's take a look at both `pkwrap_reverse_table` and `my_reverse_table` tables together to see if we can find any commonality among them:

1. `pkwrap_reverse_table` that we do not know how to use yet:
   ```
     dd052553 b87b8227 91f24b03 eb5540ff
     1d081b3b c462c807 2a7e44c6 bea38bb7
     0fd4de1a df72490a af89d5f6 bf51edb0
     18791596 5ce1a421 01a6994d 7675c91e
     263e1985 a55a246c 0ec72e50 fd48933f
     70421158 f87dccd8 39ece8a7 f584f32c
     e656cd45 4fd2c2e0 7cf06341 c52b3cb6
     00fc6f9d ac38bc74 d70ddcda d0880cd1
     e795d37a e36883fe b9348c86 4335b480
     3d049af9 b565cf6a 5bab7f92 375faa16
     54e9e4fa bd90a036 c1201fba 22d9ef61
     4777ad71 789fb333 108efb8f 5ea95917
     128752f4 57ca6713 3006c0ae f18d981c
     2fce94b2 66cb236d 4c6bdb64 ee6009d6
     02a24e28 9c4ae2a8 46e5f773 3a5d81c3
     2d32eab1 29140b31 9b9e69a1 8abb976e
   ```

1. the reverse table that I obtained running my PL/SQL code against `pkwrap_forward_table`:
   ```
     3d6585b3 18dbe287 f152ab63 4bb5a05f
     7d687b9b 24c22867 8adea426 1e03eb17
     6f343e7a 3fd2a96a 0fe93556 1fb14d10
     78d975f6 bc410481 6106f9ad d6d5297e
     869e79e5 05ba84cc 6e278eb0 5da8f39f
     d0a271b8 58dd2c38 994c4807 55e4538c
     46b62da5 af322240 dc50c3a1 258b9c16
     605ccffd 0c981cd4 376d3c3a 30e86c31
     47f533da 43c8e35e 1994ece6 a39514e0
     9d64fa59 15c52fca bb0bdff2 97bf0a76
     b449445a 1df00096 21807f1a 82394fc1
     a7d70dd1 d8ff1393 70ee5bef be09b977
     72e7b254 b72ac773 9066200e 51edf87c
     8f2ef412 c62b83cd accb3bc4 4ec06936
     6202ae88 fcaa4208 a64557d3 9abde123
     8d924a11 89746b91 fbfec901 ea1bf7ce
   ```

It can be easily spotted that the bytes in these tables differ from one another by a fixed offset `0x60` (96 in decimal).
For example:

- `0xDD (pkwrap_reverse_table[0x00]) + 0x60 = 0x3D` (the value of `my_reverse_table[0x00]`)
- `0xB7 (pkwrap_reverse_table[0x1F]) + 0x60 = 0x17` (the value of `my_reverse_table[0x1F]`)

Hence, that could be the way that reverse table is used within Oracle code (I know that it is used in the `pkwrap_read_source` function for sure).

## References

1. [How to unwrap PL/SQL by Pete Finnigan](https://www.blackhat.com/presentations/bh-usa-06/BH-US-06-Finnigan.pdf)
1. [Unwrapping Oracle PLSQL](https://macrotoneconsulting.co.uk/images/Documents/unwrap.pdf)
1. [Unwrapping 10G wrapped PL/SQL by Anton Scheffer](https://technology.amis.nl/2009/02/03/unwrapping-10g-wrapped-plsql/)
1. [Unwrapping Oracle PL/SQL with unwrap.py by Niels Teusink](http://blog.teusink.net/2010/04/unwrapping-oracle-plsql-with-unwrappy.html)
