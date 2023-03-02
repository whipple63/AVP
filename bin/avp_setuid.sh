
# Used to shutdown postgres
kill -INT `head -1 /var/lib/postgresql/9.4/main/postmaster.pid`
