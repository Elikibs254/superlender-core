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
        
        # Auto-build the tables if they don't exist yet
        self._setup_tables()
        print("Successfully connected to the MySQL database engine!")

    def _setup_tables(self):
        """Creates the borrowers table safely in the cloud."""
        table_sql = """
        CREATE TABLE IF NOT EXISTS borrowers (
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
        INSERT INTO borrowers (phone_number, national_id) 
        VALUES (%s, %s) 
        ON DUPLICATE KEY UPDATE national_id = %s
        """
        self.cursor.execute(sql, (phone_number, national_id, national_id))
        self.connection.commit()

    def get_user(self, phone_number):
        """Fetches a specific user profile from the database."""
        sql = "SELECT * FROM borrowers WHERE phone_number = %s"
        self.cursor.execute(sql, (phone_number,))
        return self.cursor.fetchone()