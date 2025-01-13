import environ
from pathlib import Path
import os

env = environ.Env()

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

ROOT_DIR = environ.Path(__file__) - 2
PROJ_DIR = ROOT_DIR.path("budgetportal")


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-ebua)1agh3++5!02kr9#josqi-5-#=n1u!)beoqp=h)d=ji_ce'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

SITE_ID = 1


# Application definition

INSTALLED_APPS = [
    
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail.core",
    'taggit',
    'budgetportal.apps.BudgetPortalConfig',
    'performance',
    'provincial_infrastructure',
    'public_entities',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    # "allauth.socialaccount.providers.google",
    'autoslug',    
    'django.contrib.humanize',
    'markdownify',    
    "django_q",
    "import_export",
    'django.contrib.sites',
    "adminplus",
    "pipeline",
    "rest_framework",
    "adminsortable",
    "ckeditor",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CONSTANCE_CONFIG = {
    "EQPRS_DATA_ENABLED": (
        True,
        "enabling / disabling performance data summary on department page",
        bool,
    ),
    "IN_YEAR_SPENDING_ENABLED": (
        False,
        "enabling / disabling presenting in-year spending on department page",
        bool,
    ),
}

SOLR_URL = os.environ["SOLR_URL"]
# SOLR_URL = "http://localhost:8983/solr/budgetportal"


HAYSTACK_CONNECTIONS = {
    "default": {
        'ENGINE': 'haystack.backends.solr_backend.SolrEngine',
        'URL': os.environ["SOLR_URL"],
    }
}

AUTHENTICATION_BACKENDS = (
    # Needed to login by username in Django admin, regardless of `allauth`
    "django.contrib.auth.backends.ModelBackend",
    # `allauth` specific authentication methods, such as login by e-mail
    "allauth.account.auth_backends.AuthenticationBackend",
)

PIPELINE = {
    "STYLESHEETS": {
        "css": {
            "source_filenames": ("stylesheets/app.scss",),
            "output_filename": "stylesheets/app.css",
        },
        "vulekamali-webflow-css": {
            "source_filenames": ("scss/vulekamali-webflow.scss",),
            "output_filename": "vulekamali-webflow.css",
        },
        "admin": {
            "source_filenames": ("stylesheets/admin.scss",),
            "output_filename": "stylesheets/admin.css",
        },
    },
    "JAVASCRIPT": {
        "js": {"source_filenames": ("javascript/app.js",), "output_filename": "app.js"}
    },
    "CSS_COMPRESSOR": None,
    "JS_COMPRESSOR": None,
    "COMPILERS": ("budgetportal.pipeline.PyScssCompiler",),
}

COMMENTS_ENABLED = os.environ.get("COMMENTS_ENABLED", "false").lower() == "true"

# DJANGO_Q_SYNC = os.environ.get("DJANGO_Q_SYNC", "false").lower() == "true"
DJANGO_Q_SYNC = False


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 20,
}


Q_CLUSTER = {
    "name": "DjangoQ",
    "workers": 1,
    "max_attempts": 1,
    "timeout": 60 * 60 * 6,  # 6 hours - Timeout a task after this many seconds
    "retry": 60 * 60 * 6 + 1,  # 6 hours - Seconds to wait before retrying a task
    "queue_limit": 1,
    "bulk": 1,
    "orm": "default",  # Use Django ORM as storage backend
    "poll": 10,  # Check for queued tasks this frequently (seconds)
    "save_limit": 0,
    "ack_failures": True,  # Dequeue failed tasks
    "sync": DJANGO_Q_SYNC,
}

ROOT_URLCONF = 'budgetportal.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        "DIRS": [str(ROOT_DIR.path("assets/js"))],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'budgetportal.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
# '192.168.56.1'

DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'NAME': 'budgetportal',
        'USER': 'budgetportaluser',
        'PASSWORD': 'devpassword',
        'HOST': os.environ["DB_HOST"],
        'PORT': '1433',
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',  # Ensure the driver is installed
        },
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.7/howto/static-files/
STATICFILES_DIRS = [
    str(ROOT_DIR.path("assets")),
    str(ROOT_DIR.path("budgetportal/static")),
    str(ROOT_DIR.path("packages/webapp/build/static")),
]


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

# where the compiled assets go
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
# the URL for assets
STATIC_URL = "/static/"

MEDIA_ROOT = os.path.join(BASE_DIR, "media")
MEDIA_URL = "/media/"

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

WAGTAIL_SITE_NAME = "Vulekamali"
