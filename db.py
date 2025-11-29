import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from contextlib import contextmanager

# Database connection
DATABASE_URL = "postgresql://neondb_owner:npg_DGC8JvyVwKr6@ep-polished-mouse-a9q3hfnh-pooler.gwc.azure.neon.tech/neondb?sslmode=require&channel_binding=require"  
connection_pool = None

try:
    connection_pool = psycopg2.pool.SimpleConnectionPool(
        1,  
        10,  
        DATABASE_URL,
        sslmode='require'
    )
    print("✅ PostgreSQL connection pool created")
except Exception as e:
    print(f"❌ PostgreSQL connection failed: {e}")

@contextmanager
def get_connection():
    conn = connection_pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        connection_pool.putconn(conn)

def init_db():
    with get_connection() as conn:
        c = conn.cursor()
        
        # Classroom Table
        c.execute("""
        CREATE TABLE IF NOT EXISTS classrooms (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Device Table
        c.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            classroom_id INTEGER NOT NULL,
            access_id TEXT NOT NULL,
            access_key TEXT NOT NULL,
            device_id TEXT NOT NULL,
            api_endpoint TEXT NOT NULL,
            status TEXT DEFAULT 'offline',
            switch_code TEXT DEFAULT 'switch',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (classroom_id) REFERENCES classrooms (id) ON DELETE CASCADE,
            UNIQUE(classroom_id, name)
        )
        """)
        
        # Data Table
        c.execute("""
        CREATE TABLE IF NOT EXISTS energy_usage (
            id SERIAL PRIMARY KEY,
            device_id INTEGER NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            power REAL,
            voltage REAL,
            current REAL,
            FOREIGN KEY (device_id) REFERENCES devices (id) ON DELETE CASCADE,
            UNIQUE(device_id, timestamp)
        )
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_device_timestamp 
        ON energy_usage(device_id, timestamp)
        """)
        
        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_classroom_device 
        ON devices(classroom_id)
        """)
            
# CLASSROOM FUNCTIONS
def add_classroom(name: str):
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('INSERT INTO classrooms (name) VALUES (%s)', (name,))


def get_all_classrooms():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT id, name FROM classrooms ORDER BY name')
        rows = c.fetchall()
        return rows

def delete_classroom(classroom_id: int):
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('DELETE FROM classrooms WHERE id = %s', (classroom_id,))

def get_classroom_devices(classroom_id: int):
    with get_connection() as conn:
        c = conn.cursor()
    
        c.execute('''
            SELECT id, name, classroom_id, access_id, access_key, device_id, api_endpoint, status, switch_code 
            FROM devices 
            WHERE classroom_id = %s 
            ORDER BY name
        ''', (classroom_id,))
        rows = c.fetchall()
        return rows

def get_classroom_device_stats(classroom_id: int):
    with get_connection() as conn:
        c = conn.cursor()

        c.execute('SELECT COUNT(*) FROM devices WHERE classroom_id = %s', (classroom_id,))
        total = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM devices WHERE classroom_id = %s AND status = %s', (classroom_id, 'on'))
        on_count = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM devices WHERE classroom_id = %s AND status = %s', (classroom_id, 'off'))
        off_count = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM devices WHERE classroom_id = %s AND status = %s', (classroom_id, 'offline'))
        offline_count = c.fetchone()[0]

        return {
            'total': total,
            'on': on_count,
            'off': off_count,
            'offline': offline_count
        }

# DEVICE FUNCTIONS
def add_device(name: str, classroom_id: int, access_id: str, access_key: str, device_id: str, api_endpoint: str):
    with get_connection() as conn:
        c = conn.cursor()
    
        c.execute('''
            INSERT INTO devices (name, classroom_id, access_id, access_key, device_id, api_endpoint, status) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (name, classroom_id, access_id, access_key, device_id, api_endpoint, 'offline'))

def get_all_devices():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT id, name, classroom_id, access_id, access_key, device_id, api_endpoint, status, switch_code 
            FROM devices 
            ORDER BY name
        ''')
        rows = c.fetchall()
        return rows

def delete_device(device_id: int):
    with get_connection() as conn:
        c = conn.cursor()
    
        c.execute('DELETE FROM devices WHERE id = %s', (device_id,))


def update_device_status(device_id: int, status: str):
    with get_connection() as conn:
        c = conn.cursor()
    
        c.execute('UPDATE devices SET status = %s WHERE id = %s', (status, device_id))


def update_device_switch_code(device_id: int, switch_code: str):
    with get_connection() as conn:
        c = conn.cursor()
    
        c.execute('UPDATE devices SET switch_code = %s WHERE id = %s', (switch_code, device_id))

def get_device_switch_code(device_id: int):
    with get_connection() as conn:
        c = conn.cursor()
    
        c.execute('SELECT switch_code FROM devices WHERE id = %s', (device_id,))
        result = c.fetchone()
        return result[0] if result else "switch"

def get_device_status(device_id: int):
    with get_connection() as conn:
        c = conn.cursor()
    
        c.execute('SELECT status FROM devices WHERE id = %s', (device_id,))
        result = c.fetchone()
        return result[0] if result else "offline"


def insert_reading(device_id: int, timestamp: str, power: float, voltage: float, current: float):
    with get_connection() as conn:
        c = conn.cursor()
        try:
            c.execute('''
                INSERT INTO energy_usage (device_id, timestamp, power, voltage, current) 
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (device_id, timestamp) 
                DO UPDATE SET power = %s, voltage = %s, current = %s
            ''', (device_id, timestamp, power, voltage, current, power, voltage, current))

        except Exception as e:
            print(f"Error inserting reading: {e}")

def fetch_all(device_id: int):
    with get_connection() as conn:
        c = conn.cursor()
    
        c.execute('''
            SELECT timestamp, power, voltage, current 
            FROM energy_usage 
            WHERE device_id = %s 
            ORDER BY timestamp
        ''', (device_id,))
        rows = c.fetchall()
        return rows

if __name__ == '__main__':
    init_db()
    print("✅ Database initialized successfully!")
    print("🐘 Using PostgreSQL")
