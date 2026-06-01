import mysql.connector

class SuperLenderEngine:
    def __init__(self, host, database, user, password):
        """Initializes the connection to the MySQL database engine."""
        self.connection = mysql.connector.connect(
            host=host,
            database=database,
            user=user,
            password=password,
            autocommit=True
        )
        # dictionary=True allows us to read rows like loan['balance_remaining']
        self.cursor = self.connection.cursor(dictionary=True)
        print("Successfully connected to the MySQL database engine!")