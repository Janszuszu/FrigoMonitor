import sqlite3
conn = sqlite3.connect('/home/yan/FrigoMonitor/backend/frigomonitor.db')
conn.execute('DROP TABLE IF EXISTS _alembic_tmp_sensors')
conn.commit()
conn.close()
print('Cleaned up')
