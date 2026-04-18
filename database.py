import psycopg2
from psycopg2 import extras
import os

class Database:
    def __init__(self, db_url):
        if db_url and db_url.startswith("postgres://"):
            self.db_url = db_url.replace("postgres://", "postgresql://", 1)
        else:
            self.db_url = db_url
        
        # Automatically set up tables if they don't exist
        self.init_db()

    def get_connection(self):
        return psycopg2.connect(self.db_url)

    def init_db(self):
        """Checks for tables and creates them if they are missing."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                # 1. Create Users Table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL,
                        role TEXT DEFAULT 'staff',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)

                # 2. Create Customers Table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS customers (
                        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                        first_name TEXT NOT NULL,
                        last_name TEXT NOT NULL,
                        phone TEXT NOT NULL,
                        id_number TEXT UNIQUE NOT NULL,
                        created_by UUID REFERENCES users(id),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)

                # 3. Create Loans Table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS loans (
                        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                        customer_id UUID REFERENCES customers(id),
                        amount_requested DECIMAL(12, 2) NOT NULL,
                        interest_rate DECIMAL(5, 2) DEFAULT 10.0,
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)

                # 4. Optional: Create a default admin if 'users' is empty
                cur.execute("SELECT COUNT(*) FROM users")
                if cur.fetchone()[0] == 0:
                    cur.execute("""
                        INSERT INTO users (username, password, role) 
                        VALUES ('admin', 'password123', 'admin')
                    """)
                
                conn.commit()
                print("Database initialization complete (Tables checked/created).")
        except Exception as e:
            print(f"Error during database init: {e}")
            if conn: conn.rollback()
        finally:
            if conn: conn.close()

    # --- REMAINING METHODS STAY THE SAME ---
    
    def get_user_by_username(self, username):
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
                return cur.fetchone()
        except Exception as e:
            print(f"DB Error (Get User): {e}")
            return None
        finally:
            if conn: conn.close()

    def add_customer(self, first_name, last_name, phone, id_number, created_by):
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO customers (first_name, last_name, phone, id_number, created_by)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                """, (first_name, last_name, phone, id_number, created_by))
                new_id = cur.fetchone()[0]
                conn.commit()
                return new_id
        except Exception as e:
            print(f"DB Error (Add Customer): {e}")
            if conn: conn.rollback()
            return None
        finally:
            if conn: conn.close()

    def get_dashboard_stats(self):
        conn = None
        stats = {'user_count': 0, 'active_loans': 0, 'total_loan_value': 0}
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                cur.execute("SELECT COUNT(*) as count FROM users")
                u_res = cur.fetchone()
                if u_res: stats['user_count'] = u_res['count']

                cur.execute("""
                    SELECT 
                        COUNT(*) as count, 
                        COALESCE(SUM(amount_requested), 0) as total 
                    FROM loans 
                    WHERE status = 'active'
                """)
                l_res = cur.fetchone()
                if l_res:
                    stats['active_loans'] = l_res['count']
                    stats['total_loan_value'] = l_res['total']
            return stats
        except Exception as e:
            print(f"DB Error (Stats): {e}")
            return stats
        finally:
            if conn: conn.close()
