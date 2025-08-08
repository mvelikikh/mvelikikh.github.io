set echo on
conn / as sysdba
alter session set container=pdb;

alter session set events 'no_such_table errorstack(1)';
oradebug setmypid
oradebug eventdump session
select * from no_such_table1;
!tail -50 ~/alert_orcl.log

exec dbms_session.sleep(10)

alter session set events 'cannot_insert_null incident("NULL_INSERTION")';
oradebug eventdump session
create table t(n int not null);
insert into t values (null);
!tail -50 ~/alert_orcl.log
