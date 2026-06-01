import mysql.connector

class SuperLenderEngine:
    def __init__(self, host, database, user, password, port=3306):
        self.connection = mysql.connector.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        
        # dictionary=True allows us to read rows cleanly like user['balance']
        self.cursor = self.connection.cursor(dictionary=True)
        
        # Auto-build the new tables if they don't exist yet
        self._setup_tables()
        print("Successfully connected to the MySQL database engine!")

    def _setup_tables(self):
        """Creates the customers table safely in the cloud."""
        table_sql = """
        CREATE TABLE IF NOT EXISTS customers (
            phone_number VARCHAR(20) PRIMARY KEY,
            national_id VARCHAR(20) NOT NULL,
            loan_limit INT DEFAULT 500,
            balance INT DEFAULT 0
        )
        """
        self.cursor.execute(table_sql)
        self.connection.commit()

    def create_user(self, phone_number, national_id):
        """Saves a new user profile permanently to the cloud database."""
        sql = """
        INSERT INTO customers (phone_number, national_id) 
        VALUES (%s, %s) 
        ON DUPLICATE KEY UPDATE national_id = %s
        """
        self.cursor.execute(sql, (phone_number, national_id, national_id))
        self.connection.commit()

    def get_user(self, phone_number):
        """Fetches a specific user profile from the database."""
        sql = "SELECT * FROM customers WHERE phone_number = %s"
        self.cursor.execute(sql, (phone_number,))
        return self.cursor.fetchone()
    def get_dashboard_metrics(self):
        """Calculates real-time totals for the web dashboard."""
        self.cursor.execute("SELECT COUNT(*) as total_users FROM customers")
        users = self.cursor.fetchone()['total_users']
        
        self.cursor.execute("SELECT SUM(balance) as total_loaned FROM customers")
        loaned = self.cursor.fetchone()['total_loaned'] or 0
        
        self.cursor.execute("SELECT SUM(loan_limit) as total_limits FROM customers")
        limits = self.cursor.fetchone()['total_limits'] or 0
        
        self.cursor.execute("SELECT phone_number, national_id, balance, loan_limit FROM customers LIMIT 10")
        recent = self.cursor.fetchall()
        
        return {
            "total_users": users,
            "total_loaned": loaned,
            "total_limits": limits,
            "recent_customers": recent
        }
    def delete_user(self, phone_number):
        """Hard deletes a user from the MySQL database."""
        self.cursor.execute("DELETE FROM customers WHERE phone_number = %s", (phone_number,))
        self.connection.commit()