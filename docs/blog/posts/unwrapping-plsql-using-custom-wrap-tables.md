---
categories:
  - Oracle
date:
  created: 2019-09-08T18:15:00
description: >-
  Demonstrate how to use custom wrap tables to affect Oracle wrap behavior.
tags:
  - Code symbol
  - PL/SQL
---

# Unwrapping PL/SQL: Using Custom Wrap Tables

A practical demonstration of how to use custom wrap tables to affect Oracle wrap behavior.

<!-- more -->

The previous article in this series:

- [Unwrapping PL/SQL: a Systematic Approach](unwrapping-plsql-a-systematic-approach.md)

As a bonus, I decided to apply that discovered knowledge about Oracle Wrap tables.

Thus, I created my own version of the **oracle** binary and put trivial wrap tables in it - the ones keeping all bytes the same:

``` hl_lines="3 21 39 57"
$ diff <(xxd oracle) <(xxd /tmp/oracle_modified)
19775119,19775150c19775119,19775150
-- pkwrap_reverse_table
< 12dbe8e0:dd05 2553 b87b 8227 91f2 4b03 eb55 40ff  ..%S.{.'..K..U@.
< 12dbe8f0:1d08 1b3b c462 c807 2a7e 44c6 bea3 8bb7  ...;.b..*~D.....
< 12dbe900:0fd4 de1a df72 490a af89 d5f6 bf51 edb0  .....rI......Q..
< 12dbe910:1879 1596 5ce1 a421 01a6 994d 7675 c91e  .y..\..!...Mvu..
< 12dbe920:263e 1985 a55a 246c 0ec7 2e50 fd48 933f  &>...Z$l...P.H.?
< 12dbe930:7042 1158 f87d ccd8 39ec e8a7 f584 f32c  pB.X.}..9......,
< 12dbe940:e656 cd45 4fd2 c2e0 7cf0 6341 c52b 3cb6  .V.EO...|.cA.+<.
< 12dbe950:00fc 6f9d ac38 bc74 d70d dcda d088 0cd1  ..o..8.t........
< 12dbe960:e795 d37a e368 83fe b934 8c86 4335 b480  ...z.h...4..C5..
< 12dbe970:3d04 9af9 b565 cf6a 5bab 7f92 375f aa16  =....e.j[...7_..
< 12dbe980:54e9 e4fa bd90 a036 c120 1fba 22d9 ef61  T......6. .."..a
< 12dbe990:4777 ad71 789f b333 108e fb8f 5ea9 5917  Gw.qx..3....^.Y.
< 12dbe9a0:1287 52f4 57ca 6713 3006 c0ae f18d 981c  ..R.W.g.0.......
< 12dbe9b0:2fce 94b2 66cb 236d 4c6b db64 ee60 09d6  /...f.#mLk.d.`..
< 12dbe9c0:02a2 4e28 9c4a e2a8 46e5 f773 3a5d 81c3  ..N(.J..F..s:]..
< 12dbe9d0:2d32 eab1 2914 0b31 9b9e 69a1 8abb 976e  -2..)..1..i....n
---
-- modified pkwrap_reverse_table
> 12dbe8e0:a0a1 a2a3 a4a5 a6a7 a8a9 aaab acad aeaf  ................
> 12dbe8f0:b0b1 b2b3 b4b5 b6b7 b8b9 babb bcbd bebf  ................
> 12dbe900:c0c1 c2c3 c4c5 c6c7 c8c9 cacb cccd cecf  ................
> 12dbe910:d0d1 d2d3 d4d5 d6d7 d8d9 dadb dcdd dedf  ................
> 12dbe920:e0e1 e2e3 e4e5 e6e7 e8e9 eaeb eced eeef  ................
> 12dbe930:f0f1 f2f3 f4f5 f6f7 f8f9 fafb fcfd feff  ................
> 12dbe940:0001 0203 0405 0607 0809 0a0b 0c0d 0e0f  ................
> 12dbe950:1011 1213 1415 1617 1819 1a1b 1c1d 1e1f  ................
> 12dbe960:2021 2223 2425 2627 2829 2a2b 2c2d 2e2f   !"#$%&'()*+,-./
> 12dbe970:3031 3233 3435 3637 3839 3a3b 3c3d 3e3f  0123456789:;<=>?
> 12dbe980:4041 4243 4445 4647 4849 4a4b 4c4d 4e4f  @ABCDEFGHIJKLMNO
> 12dbe990:5051 5253 5455 5657 5859 5a5b 5c5d 5e5f  PQRSTUVWXYZ[\]^_
> 12dbe9a0:6061 6263 6465 6667 6869 6a6b 6c6d 6e6f  `abcdefghijklmno
> 12dbe9b0:7071 7273 7475 7677 7879 7a7b 7c7d 7e7f  pqrstuvwxyz{|}~.
> 12dbe9c0:8081 8283 8485 8687 8889 8a8b 8c8d 8e8f  ................
> 12dbe9d0:9091 9293 9495 9697 9899 9a9b 9c9d 9e9f  ................

-- pkwrap_forward_table
< 12dbe9e0:7038 e00b 9101 c917 11de 27f6 7e79 4820  p8........'.~yH
< 12dbe9f0:b852 c0c7 f532 9fbf 3042 2312 cf10 3faa  .R...2..0B#...?.
< 12dbea00:a937 acd6 4602 4007 e3f4 186d 5ff0 4ad0  .7..F.@....m_.J.
< 12dbea10:c8f7 f1b7 898d a79c 7558 ec13 6e90 414f  ........uX..n.AO
< 12dbea20:0e6b 518c 1a63 e8b0 4d26 e50a d83b e264  .kQ..c..M&...;.d
< 12dbea30:4b2d c203 a00d 61c4 53be 4598 34ed bc9d  K-....a.S.E.4...
< 12dbea40:ddaf 156a db95 d4c6 85fa 97d9 47d7 ff72  ...j........G..r
< 12dbea50:50b3 25eb 773d 3cb1 b431 8305 6855 199a  P.%.w=<..1..hU..
< 12dbea60:8fee 0686 5d43 8bc1 7d29 fc1e 8acd b9bb  ....]C..})......
< 12dbea70:a508 9b4e d281 33fe ce3a 92f8 e473 f9b5  ...N..3..:...s..
< 12dbea80:a6fb e11d 3644 395b e7bd 9e99 74b2 cb28  ....6D9[....t..(
< 12dbea90:2ff3 d3b6 8e94 6f1f 0488 abfd 76a4 1c2c  /.....o.....v..,
< 12dbeaa0:caa8 66ef 146c 1b49 163e c5d5 5662 d196  ..f..l.I.>..Vb..
< 12dbeab0:7c7f 6582 212a df78 57ad 7bda 7a00 2224  |.e.!*.xW.{.z."$
< 12dbeac0:6735 e684 a2e9 6080 5aa1 f20c 592e dcae  g5....`.Z...Y...
< 12dbead0:69cc 095e c35c 2bea 5493 a3ba 714c 870f  i..^.\+.T...qL..
---
-- modified pkwrap_forward_tble
> 12dbe9e0:6061 6263 6465 6667 6869 6a6b 6c6d 6e6f  `abcdefghijklmno
> 12dbe9f0:7071 7273 7475 7677 7879 7a7b 7c7d 7e7f  pqrstuvwxyz{|}~.
> 12dbea00:8081 8283 8485 8687 8889 8a8b 8c8d 8e8f  ................
> 12dbea10:9091 9293 9495 9697 9899 9a9b 9c9d 9e9f  ................
> 12dbea20:a0a1 a2a3 a4a5 a6a7 a8a9 aaab acad aeaf  ................
> 12dbea30:b0b1 b2b3 b4b5 b6b7 b8b9 babb bcbd bebf  ................
> 12dbea40:c0c1 c2c3 c4c5 c6c7 c8c9 cacb cccd cecf  ................
> 12dbea50:d0d1 d2d3 d4d5 d6d7 d8d9 dadb dcdd dedf  ................
> 12dbea60:e0e1 e2e3 e4e5 e6e7 e8e9 eaeb eced eeef  ................
> 12dbea70:f0f1 f2f3 f4f5 f6f7 f8f9 fafb fcfd feff  ................
> 12dbea80:0001 0203 0405 0607 0809 0a0b 0c0d 0e0f  ................
> 12dbea90:1011 1213 1415 1617 1819 1a1b 1c1d 1e1f  ................
> 12dbeaa0:2021 2223 2425 2627 2829 2a2b 2c2d 2e2f   !"#$%&'()*+,-./
> 12dbeab0:3031 3233 3435 3637 3839 3a3b 3c3d 3e3f  0123456789:;<=>?
> 12dbeac0:4041 4243 4445 4647 4849 4a4b 4c4d 4e4f  @ABCDEFGHIJKLMNO
> 12dbead0:5051 5253 5455 5657 5859 5a5b 5c5d 5e5f  PQRSTUVWXYZ[\]^_
```

Remember, this wrap process, which uses modified substitution tables, should hold the following invariant to keep bytes the same:
`MOD(pkwrap_reverse_table[BYTE] + 0x60, 0x100) = pkwrap_forward_table[MOD(BYTE + 0xA0, 0x100)] = BYTE` for all `BYTE`s from 0 to 255 (it was demonstrated in the first part of this series).

Here is a sample package that I wrapped using that modified oracle binary:

```sql hl_lines="87"
SQL> with src as (
  2    select q'!package test_pkg
  3  is
  4  procedure p1;
  5  function f1 return varchar2;
  6  end;!' txt
  7      from dual),
  8    wrap as (
  9      select dbms_ddl.wrap( 'create ' || src.txt ) wrap
 10        from src)
 11  select wrap wrapped_code
 12    from wrap
 13  /

WRAPPED_CODE
--------------------------------------------------------------------------------
create package test_pkg wrapped
a000000
369
abcd
abcd
abcd
abcd
abcd
abcd
abcd
abcd
abcd
abcd
abcd
abcd
abcd
abcd
abcd
9
44 81
kuXPwLaDK0xzws78Nfs5dvIfvtl42gtwdPZ2dHdVKEktLokvyE7n8gzmCgjyd3Z1CQ1yVQgw
tOZyC/VzDvH091NwM1QIcg0JDfJTCHMMcvZwDDKy5nL1c7FmAACeSxJa


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
 20        from src)
 21  select wrap wrapped_code
 22    from wrap
 23  /

WRAPPED_CODE
--------------------------------------------------------------------------------
create package body test_pkg wrapped
a000000
369
abcd
abcd
abcd
abcd
abcd
abcd
abcd
abcd
abcd
abcd
abcd
abcd
abcd
abcd
abcd
b
b8 eb
Fhyioql6UlwVZh69G4MDdFUfl9V42j1NPQvCMBR0zq94W3URUzeLQ5q81mB8Ca9JwSmTFBFE
bP8/tigOd3DcV1D6rFqE2psrTLdxyq/HIGwnAnuNJjFCkIsGgD47r5XLvWIIrsuWIrbIcDiC
3FWixtbSnDP1pcs+xZDidkZ2lnAty/2mEkimEk0iHa0naCQwxsQE86I+KS6/R/+ln1uM0/v+
HIpff6HVB57RL3k=
```

As it is intended, there is no need to use the `pkwrap_reverse_table` to unwrap that code - it is enough to unzip it:

```sql
SQL> select mycompress.inflate(substr(utl_encode.base64_decode(utl_raw.cast_to_raw('Fhyioql6UlwVZh69G4MDdFUfl9V42j1NPQvCMBR0zq94W3URUzeLQ5q81mB8Ca9JwSmTFBFEbP8/tigOd3DcV1D6rFqE2psrTLdxyq/HIGwnAnuNJjFCkIsGgD47r5XL
vWIIrsuWIrbIcDiC3FWixtbSnDP1pcs+xZDidkZ2lnAty/2mEkimEk0iHa0naCQwxsQE86I+KS6/R/+ln1uM0/v+HIpff6HVB57RL3k=')), 41)) unwrapped_code from dual
  2  /

UNWRAPPED_CODE
----------------------------------------------------
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

That wrapped code can be correctly compiled as well:

```sql hl_lines="60 61"
SQL> drop package test_pkg
  2  /

Package dropped.

SQL> create package test_pkg wrapped
  2  a000000
  3  369
  4  abcd
  5  abcd
  6  abcd
  7  abcd
  8  abcd
  9  abcd
 10  abcd
 11  abcd
 12  abcd
 13  abcd
 14  abcd
 15  abcd
 16  abcd
 17  abcd
 18  abcd
 19  9
 20  44 81
 21  kuXPwLaDK0xzws78Nfs5dvIfvtl42gtwdPZ2dHdVKEktLokvyE7n8gzmCgjyd3Z1CQ1yVQgw
 22  tOZyC/VzDvH091NwM1QIcg0JDfJTCHMMcvZwDDKy5nL1c7FmAACeSxJa
 23  /

Package created.

SQL> create package body test_pkg wrapped
  2  a000000
  3  369
  4  abcd
  5  abcd
  6  abcd
  7  abcd
  8  abcd
  9  abcd
 10  abcd
 11  abcd
 12  abcd
 13  abcd
 14  abcd
 15  abcd
 16  abcd
 17  abcd
 18  abcd
 19  b
 20  b8 eb
 21  Fhyioql6UlwVZh69G4MDdFUfl9V42j1NPQvCMBR0zq94W3URUzeLQ5q81mB8Ca9JwSmTFBFE
 22  bP8/tigOd3DcV1D6rFqE2psrTLdxyq/HIGwnAnuNJjFCkIsGgD47r5XLvWIIrsuWIrbIcDiC
 23  3FWixtbSnDP1pcs+xZDidkZ2lnAty/2mEkimEk0iHa0naCQwxsQE86I+KS6/R/+ln1uM0/v+
 24  HIpff6HVB57RL3k=
 25  /

Package body created.

SQL> exec test_pkg.p1
123

PL/SQL procedure successfully completed.
```

Thus, the unwrapping can be now done without using that substitution table - I made the [step 3](unwrapping-plsql-a-systematic-approach.md#wrap-process) (obfuscation of zipped code) an effective noop operation keeping all bytes in place:

```sql
SQL> with wrap as (
  2      select 'create package body test_pkg wrapped
  3  a000000
  4  369
  5  abcd
  6  abcd
  7  abcd
  8  abcd
  9  abcd
 10  abcd
 11  abcd
 12  abcd
 13  abcd
 14  abcd
 15  abcd
 16  abcd
 17  abcd
 18  abcd
 19  abcd
 20  b
 21  b8 eb
 22  Fhyioql6UlwVZh69G4MDdFUfl9V42j1NPQvCMBR0zq94W3URUzeLQ5q81mB8Ca9JwSmTFBFE
 23  bP8/tigOd3DcV1D6rFqE2psrTLdxyq/HIGwnAnuNJjFCkIsGgD47r5XLvWIIrsuWIrbIcDiC
 24  3FWixtbSnDP1pcs+xZDidkZ2lnAty/2mEkimEk0iHa0naCQwxsQE86I+KS6/R/+ln1uM0/v+
 25  HIpff6HVB57RL3k=' wrap
 26        from dual),
 27    base64_dcd as(
 28      select substr( utl_encode.base64_decode( utl_raw.cast_to_raw(rtrim( substr( wrap.wrap, instr( wrap.wrap, chr( 10 ), 1, 20 ) + 1 ), chr(10) )  ) ), 41 ) x
 29        from wrap),
 30    subst as (
 31      select x s
 32      from base64_dcd)
 33  select mycompress.inflate( s ) unwrapped_code
 34    from subst
 35  /

UNWRAPPED_CODE
----------------------------------------
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

The last demonstration is used only to show how `pkwrap_forward_table` and `pkwrap_reverse_table` are used during Oracle Wrap process.
It has no practical meaning apart from verifying the assumption about how Oracle code uses these tables.
It is also an example of how behavior of Oracle can be changed without having access to source code by way of patching binary files used by Oracle utilities.
