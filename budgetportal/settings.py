import environ
from pathlib import Path
import os

env = environ.Env()

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(str(BASE_DIR / ".env"))

ROOT_DIR = environ.Path(__file__) - 2
PROJ_DIR = ROOT_DIR.path("budgetportal")


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-ebua)1agh3++5!02kr9#josqi-5-#=n1u!)beoqp=h)d=ji_ce"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Ensure Django does not force an additional HTTPS redirect
# SECURE_SSL_REDIRECT = True

# If using a reverse proxy like IIS, set the use_x_forwarded options
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
DJANGO_CSRF_TRUSTED_ORIGINS = "https://vulekamali.gov.za/"

ALLOWED_HOSTS = [
    "127.0.0.1",
    "10.131.171.115",
    "localhost",
    "app",
    "host.docker.internal",
    "vulekamali.gov.za",
]

# Production deployments must override this to False and use the IIS proxy as
# the only public entry point.  The proxy sends X-IIS-Client-IP only over its
# loopback connection to the container host port.
ASSISTANT_RATE_LIMIT_PER_MINUTE = int(
    os.environ.get("ASSISTANT_RATE_LIMIT_PER_MINUTE", "30")
)
ASSISTANT_CACHE = {
    "enabled": os.environ.get("ASSISTANT_CACHE_ENABLED", "false").lower() == "true",
    "require_shared_cache": os.environ.get("ASSISTANT_REQUIRE_SHARED_CACHE", "false").lower() == "true",
    "schema_version": os.environ.get("ASSISTANT_CACHE_SCHEMA_VERSION", "1"),
    "policy_revision": os.environ.get("ASSISTANT_POLICY_REVISION", "1"),
    "lock_seconds": int(os.environ.get("ASSISTANT_CACHE_LOCK_SECONDS", "35")),
    "wait_seconds": float(os.environ.get("ASSISTANT_CACHE_WAIT_SECONDS", "1.5")),
    "ttls": {
        "verified": int(os.environ.get("ASSISTANT_CACHE_VERIFIED_TTL", "1800")),
        "data_not_found": int(os.environ.get("ASSISTANT_CACHE_NOT_FOUND_TTL", "300")),
        "needs_clarification": int(os.environ.get("ASSISTANT_CACHE_CLARIFICATION_TTL", "300")),
        "out_of_scope": int(os.environ.get("ASSISTANT_CACHE_OUT_OF_SCOPE_TTL", "300")),
    },
}
ASSISTANT_FOUNDRY_GUARD = {
    "deadline_seconds": float(os.environ.get("ASSISTANT_REQUEST_DEADLINE_SECONDS", "30")),
    "max_calls_per_request": int(os.environ.get("ASSISTANT_MAX_FOUNDRY_CALLS", "4")),
    "max_tokens_per_request": int(os.environ.get("ASSISTANT_MAX_FOUNDRY_TOKENS", "1200")),
    "max_concurrent_calls": int(os.environ.get("ASSISTANT_MAX_CONCURRENT_FOUNDRY_CALLS", "8")),
    "failure_window_seconds": int(os.environ.get("ASSISTANT_FOUNDRY_FAILURE_WINDOW_SECONDS", "60")),
    "circuit_failure_threshold": int(os.environ.get("ASSISTANT_FOUNDRY_CIRCUIT_THRESHOLD", "5")),
    "circuit_cooldown_seconds": int(os.environ.get("ASSISTANT_FOUNDRY_CIRCUIT_COOLDOWN_SECONDS", "30")),
}

REDIS_URL = os.environ.get("REDIS_URL", "")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }
# ALLOWED_HOSTS = ["*"]


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
    "taggit",
    "budgetportal.apps.BudgetPortalConfig",
    "performance",
    "dataset_preparation.apps.DatasetPreparationConfig",
    "provincial_infrastructure",
    "public_entities",
    "data_validation",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    # "allauth.socialaccount.providers.google",
    "autoslug",
    "django.contrib.humanize",
    "markdownify",
    "django_q",
    "import_export",
    "django.contrib.sites",
    "adminplus",
    "pipeline",
    "rest_framework",
    "adminsortable",
    "ckeditor",
    "haystack",
]

MARKDOWNIFY_WHITELIST_TAGS = [
    "a",
    "blockquote",
    "br",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "strong",
    "ul",
]

MARKDOWNIFY_WHITELIST_ATTRS = {
    "a": ["href", "title", "rel", "target"],
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.core.middleware.SiteMiddleware",
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
        "ENGINE": "haystack.backends.solr_backend.SolrEngine",
        "URL": os.environ["SOLR_URL"],
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
    "broker_class": "budgetportal.queue_broker.SqlServerSafeORMBroker",
    "poll": int(
        os.environ.get("DJANGO_Q_POLL_SECONDS", "30")
    ),  # Check for queued tasks this frequently (seconds)
    "save_limit": 0,
    "ack_failures": True,  # Dequeue failed tasks
    "sync": DJANGO_Q_SYNC,
}

# Azure OpenAI / Microsoft Foundry configuration. Credentials are deliberately
# supplied only by the environment or Microsoft Entra ID's credential chain.
AZURE_OPENAI = {
    "endpoint": os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
    "deployment": os.environ.get("AZURE_OPENAI_DEPLOYMENT", ""),
    "api_key": os.environ.get("AZURE_OPENAI_API_KEY", ""),
    "auth_mode": os.environ.get("AZURE_OPENAI_AUTH_MODE", "api_key").lower(),
    "api_version": os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
    "entra_scope": os.environ.get(
        "AZURE_OPENAI_ENTRA_SCOPE", "https://cognitiveservices.azure.com/.default"
    ),
    "connect_timeout_seconds": float(
        os.environ.get("AZURE_OPENAI_CONNECT_TIMEOUT_SECONDS", "5")
    ),
    "read_timeout_seconds": float(
        os.environ.get("AZURE_OPENAI_READ_TIMEOUT_SECONDS", "20")
    ),
    "max_retries": int(os.environ.get("AZURE_OPENAI_MAX_RETRIES", "2")),
}
AZURE_OPENAI_ALLOWED_HOSTS = tuple(
    host.strip().lower()
    for host in os.environ.get("AZURE_OPENAI_ALLOWED_HOSTS", "").split(",")
    if host.strip()
)

VULEKAMALI_SCOPE_CONFIDENCE_THRESHOLD = float(
    os.environ.get("VULEKAMALI_SCOPE_CONFIDENCE_THRESHOLD", "0.80")
)
VULEKAMALI_SCOPE_STRUCTURED_OUTPUTS_ENABLED = (
    os.environ.get("VULEKAMALI_SCOPE_STRUCTURED_OUTPUTS_ENABLED", "true").lower()
    == "true"
)

# Optional Azure AI Content Safety Prompt Shields integration. If enabled, an
# unavailable shield fails closed in the application-level attack screen.
AZURE_CONTENT_SAFETY = {
    "enabled": os.environ.get("AZURE_CONTENT_SAFETY_ENABLED", "false").lower()
    == "true",
    "endpoint": os.environ.get("AZURE_CONTENT_SAFETY_ENDPOINT", ""),
    "api_key": os.environ.get("AZURE_CONTENT_SAFETY_API_KEY", ""),
    "auth_mode": os.environ.get("AZURE_CONTENT_SAFETY_AUTH_MODE", "api_key").lower(),
    "api_version": os.environ.get("AZURE_CONTENT_SAFETY_API_VERSION", "2024-09-01"),
    "entra_scope": os.environ.get(
        "AZURE_CONTENT_SAFETY_ENTRA_SCOPE",
        "https://cognitiveservices.azure.com/.default",
    ),
    "timeout_seconds": float(
        os.environ.get("AZURE_CONTENT_SAFETY_TIMEOUT_SECONDS", "10")
    ),
}

ROOT_URLCONF = "budgetportal.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [str(ROOT_DIR.path("assets/js"))],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "budgetportal.wsgi.application"

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
# '192.168.56.1'

DATABASES = {
    "default": {
        "ENGINE": "mssql",
        "NAME": "budgetportal",
        # Credentials are supplied only by the deployment environment. Use a
        # dedicated least-privilege application account in production rather
        # than the SQL Server administrator account.
        "USER": os.environ.get("DB_USER", ""),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "sqlserver"),
        "PORT": "1433",
        "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", 600)),
        "OPTIONS": {
            "driver": "ODBC Driver 18 for SQL Server",
            "extra_params": (
                "TrustServerCertificate=yes;"
                "Encrypt=no;"
                "Connection Timeout={};"
                "LoginTimeout={}"
            ).format(
                os.environ.get("DB_CONNECTION_TIMEOUT", "60"),
                os.environ.get("DB_LOGIN_TIMEOUT", "60"),
            ),
        },
    }
}

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

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

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

WAGTAIL_SITE_NAME = "Vulekamali"
