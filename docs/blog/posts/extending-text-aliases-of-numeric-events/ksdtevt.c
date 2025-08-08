typedef struct {
  char *alias;
  long code;
} ksdtevt_struct;

ksdtevt_struct ksdtevt[27] = {{"LOGON", 10029},
                              {"LOGOFF", 10030},
                              {"DEADLOCK", 60},
                              {"NOTIFYCRS", 39505},
                              {"CONTROL_FILE", 10000},
                              {"DB_FILES", 10222},
                              {"BEGIN", 10010},
                              {"END", 10011},
                              {"PQ_KILL_TEST", 10370},
                              {"PQ_KILL_TEST_PROC", 10372},
                              {"PQ_KILL_TEST_CODE", 10373},
                              {"KXFX", 10390},
                              {"SORT_END", 10032},
                              {"SORT_RUN", 10033},
                              {"PARSE_SQL_STATEMENT", 10035},
                              {"CREATE_REMOTE_RWS", 10036},
                              {"ALLOC_REMOTE_RWS", 10037},
                              {"QUERY_BLOCK_ALLOC", 10038},
                              {"TYPE_CHECK", 10039},
                              {"KFTRACE", 15199},
                              {"KFDEBUG", 15194},
                              {"KFSYNTAX", 15195},
                              {"KEWA_ASH_TRACE", 13740},
                              {"kea_debug_event", 13698},
                              {"KEH_TRACE", 13700},
                              {"NO_SUCH_TABLE", 942},
                              {"CANNOT_INSERT_NULL", 1400}};
