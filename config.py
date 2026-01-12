# # import os
# # from dotenv import load_dotenv

# # load_dotenv()

# # class Config:
# #     SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    
# #     # Database configuration
# #     DB_HOST = os.getenv('DB_HOST',)
# #     DB_USER = os.getenv('DB_USER', 'root')
# #     DB_PASSWORD = os.getenv('DB_PASSWORD', 'root')
# #     DB_NAME = os.getenv('DB_NAME', 'food_delivery_db')
    
# #     # MySQL URI
# #     SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
# #     SQLALCHEMY_TRACK_MODIFICATIONS = False
    
# #     # Email configuration
# #     MAIL_SERVER = os.getenv('MAIL_SERVER')
# #     MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
# #     MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
# #     MAIL_USERNAME = os.getenv('MAIL_USERNAME')
# #     MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    
# #     # Credit score ranges
# #     CREDIT_SCORE_RANGES = {
# #         'trusted': (90, 100),
# #         'good': (75, 89),
# #         'average': (50, 74),
# #         'risky': (30, 49),
# #         'blocked': (0, 29)
# #     }
    
# #     DEFAULT_CREDIT_SCORE = 70




# import os
# from dotenv import load_dotenv

# load_dotenv()

# class Config:
#     SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

#     # ✅ Flask-MySQLdb expects THESE exact names
#     MYSQL_HOST = os.getenv('DB_HOST', 'localhost')
#     MYSQL_USER = os.getenv('DB_USER', 'root')
#     MYSQL_PASSWORD = os.getenv('DB_PASSWORD', 'root')
#     MYSQL_DB = os.getenv('DB_NAME', 'food_delivery_db')
#     MYSQL_CURSORCLASS = 'DictCursor'

#     # ✅ Mail config
#     MAIL_SERVER = os.getenv('MAIL_SERVER')
#     MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
#     MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
#     MAIL_USERNAME = os.getenv('MAIL_USERNAME')
#     MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')

#     # Credit score ranges
#     CREDIT_SCORE_RANGES = {
#         'trusted': (90, 100),
#         'good': (75, 89),
#         'average': (50, 74),
#         'risky': (30, 49),
#         'blocked': (0, 29)
#     }

#     DEFAULT_CREDIT_SCORE = 70




import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

    # Flask-MySQLdb configuration
    MYSQL_HOST = os.getenv('DB_HOST', 'localhost')
    MYSQL_USER = os.getenv('DB_USER', 'root')
    MYSQL_PASSWORD = os.getenv('DB_PASSWORD', 'root')
    MYSQL_DB = os.getenv('DB_NAME', 'food_delivery_db')
    # REMOVE or comment out this line:
    # MYSQL_CURSORCLASS = 'DictCursor'
    # Or change to:
    MYSQL_CURSORCLASS = 'Cursor'

    # Mail configuration
    MAIL_SERVER = os.getenv('MAIL_SERVER')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')

    # Credit score ranges
    CREDIT_SCORE_RANGES = {
        'trusted': (90, 100),
        'good': (75, 89),
        'average': (50, 74),
        'risky': (30, 49),
        'blocked': (0, 29)
    }

    DEFAULT_CREDIT_SCORE = 70