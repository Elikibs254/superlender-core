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
        
        # dictionary=True allows us to read rows like loan['balance_remaining']
        self.cursor = self.connection.cursor(dictionary=True)
        print("Successfully connected to the MySQL database engine!")