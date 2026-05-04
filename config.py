import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DB_SERVER = os.environ.get('DB_SERVER', 'localhost')
    DB_NAME = os.environ.get('DB_NAME', 'VOC_DataBase')
    DB_DRIVER = os.environ.get('DB_DRIVER', 'ODBC+Driver+17+for+SQL+Server')

    SQLALCHEMY_DATABASE_URI = (
        f"mssql+pyodbc://@{DB_SERVER}/{DB_NAME}"
        f"?driver={DB_DRIVER}"
        "&Trusted_Connection=yes"
    )

    # JWT
    JWT_SECRET_KEY           = os.environ.get('JWT_SECRET_KEY', 'voc-jwt-secret-change-in-prod')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    JWT_TOKEN_LOCATION       = ['headers', 'cookies']
    JWT_ACCESS_COOKIE_NAME   = 'voc_token'
    JWT_COOKIE_SECURE        = False   # set True in production (HTTPS only)
    JWT_COOKIE_CSRF_PROTECT  = False   # simplified for dev

    # Active Directory
    AD_SERVER  = os.environ.get('AD_SERVER',   '192.168.4.3')
    AD_PORT    = int(os.environ.get('AD_PORT',  389))
    AD_DOMAIN  = os.environ.get('AD_DOMAIN',   'DEMO')
    AD_BASE_DN = os.environ.get('AD_BASE_DN',  'DC=demo,DC=lab')
    AD_BIND_DN = os.environ.get('AD_BIND_DN',  'ygrara@demo.lab')
    AD_BIND_PWD = os.environ.get('AD_BIND_PWD', 'pfe2026*')
    AD_USE_SSL = os.environ.get('AD_USE_SSL',  'false').lower() == 'true'


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}
